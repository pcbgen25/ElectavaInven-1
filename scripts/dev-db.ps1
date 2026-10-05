<#
.SYNOPSIS
  Local development PostgreSQL 16 without admin rights (portable, runs as current user).

.DESCRIPTION
  setup  : download binaries (once), initdb, start, create app role + database from backend/.env
  start  : start the server
  stop   : stop the server
  status : show server status

  Binaries/data live in %LOCALAPPDATA%\ElectavaCore\postgres (outside the repo).
  The server listens on localhost only. The superuser password is stored in
  electava-core/.local/postgres-superuser.txt (git-ignored).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts/dev-db.ps1 setup
#>
param([Parameter(Position = 0)][ValidateSet("setup", "start", "run", "stop", "status")][string]$Action = "status")

$ErrorActionPreference = "Stop"
$PgVersion = "16.15-5"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Root = Join-Path $env:LOCALAPPDATA "ElectavaCore\postgres"
$Bin = Join-Path $Root "pgsql\bin"
$Data = Join-Path $Root "data16"
$LogFile = Join-Path $Root "postgres.log"
$LocalDir = Join-Path $RepoRoot ".local"
$SuperPwFile = Join-Path $LocalDir "postgres-superuser.txt"
$EnvFile = Join-Path $RepoRoot "backend\.env"

function Read-DotEnv([string]$path) {
    $vars = @{}
    if (Test-Path $path) {
        foreach ($line in Get-Content $path) {
            if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') { $vars[$matches[1]] = $matches[2] }
        }
    }
    return $vars
}

function New-RandomSecret([int]$len = 24) {
    -join ((48..57) + (65..90) + (97..122) | Get-Random -Count $len | ForEach-Object { [char]$_ })
}

$envVars = Read-DotEnv $EnvFile
$Port = if ($envVars["POSTGRES_PORT"]) { $envVars["POSTGRES_PORT"] } else { "5432" }

function Install-Binaries {
    if (Test-Path (Join-Path $Bin "pg_ctl.exe")) { return }
    New-Item -ItemType Directory -Force $Root | Out-Null
    $zip = Join-Path $Root "postgresql-$PgVersion-binaries.zip"
    if (-not (Test-Path $zip)) {
        $url = "https://get.enterprisedb.com/postgresql/postgresql-$PgVersion-windows-x64-binaries.zip"
        Write-Host "Downloading $url ..."
        & curl.exe -L --fail -o $zip $url
        if ($LASTEXITCODE -ne 0) { throw "Download failed" }
    }
    Write-Host "Extracting ..."
    & tar.exe -xf $zip -C $Root pgsql/bin pgsql/lib pgsql/share
    if ($LASTEXITCODE -ne 0) { throw "Extraction failed" }
}

function Initialize-Cluster {
    if (Test-Path (Join-Path $Data "PG_VERSION")) { return }
    New-Item -ItemType Directory -Force $LocalDir | Out-Null
    if (-not (Test-Path $SuperPwFile)) { Set-Content -Path $SuperPwFile -Value (New-RandomSecret) -NoNewline }
    Write-Host "Initialising cluster in $Data ..."
    & (Join-Path $Bin "initdb.exe") -D $Data -U postgres --pwfile=$SuperPwFile --auth=scram-sha-256 -E UTF8 --no-locale
    if ($LASTEXITCODE -ne 0) { throw "initdb failed" }
    # Never expose the database beyond this machine.
    Add-Content (Join-Path $Data "postgresql.conf") "`nlisten_addresses = 'localhost'`nport = $Port`n"
}

function Test-Running {
    & (Join-Path $Bin "pg_ctl.exe") status -D $Data *> $null
    return ($LASTEXITCODE -eq 0)
}

function Start-Server {
    if (Test-Running) { Write-Host "PostgreSQL already running on port $Port."; return }
    & (Join-Path $Bin "pg_ctl.exe") start -D $Data -l $LogFile -w -t 60
    if ($LASTEXITCODE -ne 0) { throw "pg_ctl start failed - see $LogFile" }
}

function Invoke-Psql([string]$sql, [string]$db = "postgres") {
    $env:PGPASSWORD = (Get-Content $SuperPwFile -Raw).Trim()
    try {
        $out = & (Join-Path $Bin "psql.exe") -h 127.0.0.1 -p $Port -U postgres -d $db -v ON_ERROR_STOP=1 -tAc $sql
        if ($LASTEXITCODE -ne 0) { throw "psql failed: $sql" }
        return $out
    } finally { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue }
}

function Initialize-AppDatabase {
    $db = if ($envVars["POSTGRES_DB"]) { $envVars["POSTGRES_DB"] } else { "electava_core" }
    $user = if ($envVars["POSTGRES_USER"]) { $envVars["POSTGRES_USER"] } else { "electava" }
    $pw = $envVars["POSTGRES_PASSWORD"]
    if (-not $pw) { throw "POSTGRES_PASSWORD missing in backend/.env" }
    if ($pw -notmatch '^[A-Za-z0-9]+$') { throw "Use an alphanumeric POSTGRES_PASSWORD for this dev script." }
    $exists = Invoke-Psql "SELECT 1 FROM pg_roles WHERE rolname = '$user'"
    if ($exists -ne "1") {
        Invoke-Psql "CREATE ROLE $user LOGIN CREATEDB PASSWORD '$pw'" | Out-Null
        Write-Host "Created role $user"
    } else {
        Invoke-Psql "ALTER ROLE $user WITH LOGIN CREATEDB PASSWORD '$pw'" | Out-Null
    }
    $dbExists = Invoke-Psql "SELECT 1 FROM pg_database WHERE datname = '$db'"
    if ($dbExists -ne "1") {
        Invoke-Psql "CREATE DATABASE $db OWNER $user ENCODING 'UTF8'" | Out-Null
        Write-Host "Created database $db"
    }
    # pg_trgm powers component search. It is a trusted extension, but create it as superuser
    # in template1 too so pytest's test database inherits it.
    Invoke-Psql "CREATE EXTENSION IF NOT EXISTS pg_trgm" $db | Out-Null
    Invoke-Psql "CREATE EXTENSION IF NOT EXISTS pg_trgm" "template1" | Out-Null
}

switch ($Action) {
    "setup" { Install-Binaries; Initialize-Cluster; Start-Server; Initialize-AppDatabase; Write-Host "PostgreSQL ready on 127.0.0.1:$Port" }
    "start" { Start-Server }
    "run" { Write-Host "Running PostgreSQL in the foreground on 127.0.0.1:$Port (Ctrl+C to stop)"; & (Join-Path $Bin "postgres.exe") -D $Data }
    "stop" { & (Join-Path $Bin "pg_ctl.exe") stop -D $Data -m fast }
    "status" { & (Join-Path $Bin "pg_ctl.exe") status -D $Data }
}

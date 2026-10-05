<#
.SYNOPSIS
  Create backend/.env from backend/.env.example with freshly generated local secrets.
  Refuses to overwrite an existing .env.
#>
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Example = Join-Path $RepoRoot "backend\.env.example"
$Target = Join-Path $RepoRoot "backend\.env"

if (Test-Path $Target) { Write-Host "backend/.env already exists - leaving it unchanged."; exit 0 }

function New-RandomSecret([int]$len) {
    $chars = (48..57) + (65..90) + (97..122)
    -join (1..$len | ForEach-Object { [char]($chars | Get-Random) })
}

$content = Get-Content $Example -Raw
$content = $content -replace '(?m)^DJANGO_SECRET_KEY=.*$', "DJANGO_SECRET_KEY=$(New-RandomSecret 64)"
$content = $content -replace '(?m)^POSTGRES_PASSWORD=.*$', "POSTGRES_PASSWORD=$(New-RandomSecret 24)"
$content = $content -replace '(?m)^DEV_SEED_PASSWORD=.*$', "DEV_SEED_PASSWORD=Dev-$(New-RandomSecret 14)"
Set-Content -Path $Target -Value $content -NoNewline
Write-Host "Created backend/.env with generated secrets (git-ignored)."

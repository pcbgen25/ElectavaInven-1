# Electava Inventory — Architecture

Status: Phase 1 (foundation + component database). Last updated: Phase 1.

## 1. High-level

```
Browser / Mobile (PWA)
        │  HTTPS, same origin
        ▼
Next.js frontend (App Router, React, TypeScript, Tailwind)
        │  /api/*  → proxied (Next rewrites in dev, reverse proxy in prod)
        ▼
Django + Django REST Framework  (modular monolith)
        │                    │
        ▼                    ▼
   PostgreSQL          File storage (local FS in dev, S3-compatible in prod)
```

### Why a modular monolith
One team, one deployable, strongly relational data (BOM ↔ components ↔ stock ↔ purchasing)
that needs cross-module ACID transactions (e.g. goods receipt → stock transaction → PO
status). Microservices would turn those into distributed transactions with no benefit at
this scale. Module boundaries are enforced in code (one Django app per module, writes via
`services.py`) so a module could be extracted later if ever required (e.g. the future
marketplace).

## 2. Backend

```
backend/
  config/            settings (base/development/production/test), urls, wsgi/asgi
  apps/
    core/            shared base models, pagination, router, permission class, file validation
    accounts/        User, Role, Permission, auth endpoints, RBAC sync
    audit/           AuditLog (append-only) + audit service
    manufacturers/   Manufacturer
    components/      Category, Package, Component, Alias, SpecificationDefinition,
                     ComponentSpecification, part-number sequences, unit parsing, search
    reports/         Dashboard summary (Phase 1); reports (Phase 5)
    -- later phases --
    projects/  bom/  inventory/  suppliers/  purchasing/  documents/
```

### Authentication — decision
**Django session authentication + CSRF, served same-origin through the Next.js proxy.**

- The browser only ever talks to the Next.js origin. `/api/*` is rewritten to Django
  (dev: `next.config.ts` rewrites; prod: Nginx/Caddy routes `/api` to Gunicorn).
- Session cookie is `HttpOnly`, `SameSite=Lax`, `Secure` in production → not readable
  by JavaScript, so XSS cannot steal credentials (unlike JWT in `localStorage`).
- Unsafe methods require the `X-CSRFToken` header (DRF `SessionAuthentication`).
- Passwords hashed with Argon2 (`argon2-cffi`), PBKDF2 as fallback.
- Login is rate limited (DRF `ScopedRateThrottle`, scope `auth`).
- JWT/API-token auth can be added later **alongside** sessions for machine clients
  (vendor portal, marketplace integrations) without changing the browser flow.

### Authorization (RBAC)
- `Permission` (code e.g. `component.create`), `Role` (code e.g. `PCB_ENGINEER`,
  M2M to permissions), `User.roles` (M2M).
- The canonical permission catalog and default role grants live in
  `apps/accounts/rbac_catalog.py` and are synced to the DB on every `migrate`
  (`post_migrate`). Admins can change role grants at runtime via API; sync only adds
  missing permissions/roles and never removes custom grants.
- Every view declares `required_permissions = {"list": "component.view", ...}` and uses
  `apps.core.permissions.HasRBACPermission`. Unknown actions are **denied** by default.
- `SUPER_ADMIN` role and Django `is_superuser` have every permission.
  Only a super admin may grant the `SUPER_ADMIN` role.

### Audit
`apps/audit/services.record()` writes an `AuditLog` row (user, action, entity type/id,
old value, new value, IP, user agent). Called explicitly from services/viewset mixins —
not from model signals — so the business context is known. Sensitive keys
(`password`, `token`, `secret`, ...) are redacted. `AuditLog.save()` refuses updates and
`delete()` raises: the table is append-only at application level.

### Component search
Each component has a denormalised `search_document` (PN, MPN, name, description,
manufacturer, category, package, aliases, specification values; supplier PNs from Phase 4)
rebuilt by `components.services.rebuild_search_document()` whenever any of those change.
A PostgreSQL trigram GIN index on `UPPER(search_document)` makes `icontains` search fast
for substring matches such as `1042` or `soic`. Exact-match columns (`internal_part_number`,
`mpn_normalized`) have B-tree indexes for the KiCad matcher (Phase 2).

### Dynamic specifications
EAV restricted by definitions: `SpecificationDefinition` per category (inherited by
sub-categories) with a data type (`STRING|INTEGER|DECIMAL|BOOLEAN|ENUM`), base unit and
optional SI-prefix parsing. `ComponentSpecification` stores the value in a typed column
(`value_string`, `value_integer`, `value_decimal`, `value_boolean`) so numeric values are
sortable/filterable. `100nF` for a definition with unit `F` and SI prefixes enabled is
stored as `0.0000001` and displayed back as `100 nF`.

### Files
`STORAGES["default"]` = `FileSystemStorage` (dev, `backend/media/`) or
`storages.backends.s3.S3Storage` when `USE_S3=true`. Uploads validated by extension,
size and content signature (`apps/core/files.py`). Files are referenced by path from DB rows.

## 3. Frontend

```
frontend/src/
  app/
    login/                    public
    (app)/                    authenticated shell (sidebar + mobile bottom nav)
      dashboard/ components/ users/ settings/ ...
  components/ui/              small design-system primitives (Button, Input, Badge, ...)
  components/data-table/      server-driven table (search, sort, filter, paging, columns, CSV)
  lib/api.ts                  fetch wrapper (credentials, CSRF, error normalisation)
  lib/auth.tsx                AuthProvider: current user + permission set
  lib/nav.ts                  navigation definition with phase availability
```

- Data fetching with TanStack Query; forms with react-hook-form + zod (client validation
  mirrors but never replaces server validation).
- `middleware.ts` redirects to `/login` when there is no session cookie (UX only).
- Navigation items for unimplemented modules are shown disabled with a "Phase N" badge.
- Mobile (< 768px): top bar + bottom nav (Home, Search, Scan, BOM, More). Tables collapse
  into card lists. Scan/BOM are disabled until Phases 3/2.
- PWA: web manifest + icons + theme colour in Phase 1; service worker/offline in Phase 5.

## 4. Environments

| Env         | Settings module                     | Storage | Debug |
|-------------|-------------------------------------|---------|-------|
| development | `config.settings.development`       | local   | on    |
| test        | `config.settings.test`              | local tmp | off |
| production  | `config.settings.production`        | S3      | off, HSTS, secure cookies |

PostgreSQL must listen only on localhost/private network. Never expose it publicly.

## 5. Future extensibility (not built in V1)
Marketplace, vendor portal, customer portal, RFQ, online purchasing: planned as new Django
apps reusing `components`, `suppliers` and `purchasing` services, with separate external
auth (token/JWT) and an `organization` tenancy concept for external parties. Nothing in V1
assumes users are only internal employees beyond the role catalog.

## 6. Decision log
| # | Decision | Reason |
|---|----------|--------|
| 1 | Modular monolith | ACID across modules, small team |
| 2 | Session auth via same-origin proxy | HttpOnly cookies, built-in CSRF, no token storage in JS |
| 3 | Own Role/Permission models instead of Django Groups | Business permission codes (`bom.release`) independent of model CRUD |
| 4 | EAV with typed columns for specs | Categories define their own specs without schema changes, numeric filtering still possible |
| 5 | Denormalised search document + trigram index | One indexed column covers PN/MPN/alias/spec search |
| 6 | Explicit audit calls, not signals | Business context and user available; no hidden side effects |

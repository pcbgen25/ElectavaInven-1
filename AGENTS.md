# AGENTS.md — Electava Inventory development rules

This file is binding for every human or AI contributor working on this repository.
Read it before changing code. Keep it up to date when rules change.

## 1. What this system is

Electava Inventory is an **internal** electronics engineering management system
(components, BOMs, projects, inventory, suppliers, purchasing). It is used for real
engineering and purchasing decisions. Correctness and traceability matter more than speed
of feature delivery.

## 2. Architecture rules

1. **Modular monolith.** One Django backend, one Next.js frontend, one PostgreSQL database.
   Do not introduce microservices, message brokers or extra databases without a written
   justification in `docs/ARCHITECTURE.md` and approval.
2. **Backend owns business logic and authorization.** The frontend only renders and
   collects input. Hiding a button is UX, never security.
3. **Django apps = bounded modules.** Each app lives in `backend/apps/<module>/` and owns
   its models. Cross-module writes go through that module's `services.py`; never write
   another module's tables directly from a view.
4. **Layering inside an app:**
   - `models.py` – data + invariants that must always hold (constraints, `clean()`)
   - `services.py` – business operations (transactions, multi-model writes, audit)
   - `serializers.py` – input validation / output shape only
   - `views.py` – HTTP + permission declaration only, thin
   - `selectors.py` (optional) – complex read queries
5. **No giant files.** If a file passes ~400 lines, split it.
6. **No duplicated business logic.** Calculations such as `available = quantity - reserved`
   live in exactly one backend function.

## 3. Data rules

1. PostgreSQL only. Every schema change ships with a migration. Never edit applied migrations.
2. Use foreign keys, unique constraints and indexes. Prefer DB constraints over app checks.
3. **Never hard-delete history**: released BOMs, inventory transactions, purchase history,
   price history and audit logs are append-only.
4. Master data (components, manufacturers, categories, packages) uses **soft delete**
   (`deleted_at`). Use `PROTECT` on FKs to master data.
5. Every stock change creates an inventory transaction inside `transaction.atomic()` with
   `select_for_update()` on the affected rows.
6. A `RELEASED` BOM revision is immutable. Changes require a new revision.
7. Binary files never go into PostgreSQL. Use Django storages (local in dev, S3 in prod).

## 4. Security rules

1. No secrets in code or git. All config comes from environment variables (`.env` is
   git-ignored; `.env.example` documents keys with placeholder values).
2. Every API view declares its required permission codes (`required_permissions`).
   The default DRF permission is "authenticated + RBAC"; never use `AllowAny` except
   for login/CSRF endpoints.
3. Never log or audit passwords, tokens or secrets (see `apps/audit/services.py` redaction).
4. Validate uploads by extension **and** content; enforce max size.
5. Use the ORM. Raw SQL requires parameters and a code-review note.

## 5. Honesty rules

1. Do not create mock APIs, fake data flows or static JSON in place of real persistence.
2. A feature is "done" only when it has: model + migration, API, permission checks,
   audit (where applicable), UI, and automated tests — and those tests pass.
3. Unimplemented features must be visibly marked as such in the UI and in
   `docs/DEVELOPMENT_ROADMAP.md`.
4. Seed data is **development data** and must be labelled so. Never invent technical
   specifications for real parts — leave them empty or clearly marked as unverified.

## 6. Workflow

1. Work phase by phase (see `docs/DEVELOPMENT_ROADMAP.md`). Don't start a phase until the
   previous phase's user flow works end-to-end.
2. Before a major architectural change, document the reason in `docs/ARCHITECTURE.md`.
3. Run before committing:
   - `backend`: `python -m pytest` and `python manage.py makemigrations --check --dry-run`
   - `frontend`: `npm run lint` and `npm run build`
4. Update `docs/API.md` / `docs/DATABASE.md` when endpoints or tables change.

## 7. Conventions

- Python: PEP 8, type hints on services, `ruff` formatting.
- TypeScript: strict mode, no `any` without a comment.
- API: JSON, snake_case fields, plural resource nouns, `/api/<resource>` with no
  required trailing slash, page-number pagination `{count, next, previous, results}`.
- Errors: DRF standard `{"detail": ...}` or field errors `{"field": ["msg"]}`.
- IDs: integer primary keys internally; human identifiers (internal PN, project code) are
  unique business keys.
- Time: store UTC, display in the user's local time zone.

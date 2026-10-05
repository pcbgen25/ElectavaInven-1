# API Documentation: Electava Inventory

## 1. Overview
Electava Inventory exposes a REST API via Django REST Framework (DRF).

## 2. Authentication
- **Mechanism:** JWT (JSON Web Tokens)
- **Flow:** 
  1. POST `/api/accounts/login/` -> Receives `access` and `refresh` tokens.
  2. Pass token in header: `Authorization: Bearer <access_token>`
  3. POST `/api/accounts/token/refresh/` to renew.

## 3. Endpoints (Phase 1)

### Auth & Accounts
- `POST /api/accounts/login/`: Authenticate
- `GET /api/accounts/me/`: Get current user info & permissions
- `GET /api/accounts/users/`: List users (Admin)
- `GET /api/accounts/roles/`: List roles
- `PUT /api/accounts/users/{id}/roles/`: Assign roles

### Components & Master Data
- `GET /api/components/components/`: List all components (search, filter)
- `POST /api/components/components/`: Create a component
- `GET /api/components/components/{id}/`: Get full component details
- `PATCH /api/components/components/{id}/`: Update component
- `POST /api/components/components/{id}/upload-datasheet/`: File upload endpoint
- `GET /api/components/categories/`: Hierarchical categories
- `GET /api/components/manufacturers/`: List manufacturers
- `GET /api/components/packages/`: List packages

### Audit
- `GET /api/audit/logs/`: View system audit logs (Admin)

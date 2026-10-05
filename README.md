# Electava Inventory

An internal Electronics Engineering Management System for managing components, BOMs, projects, inventory, suppliers, and purchasing.

## Architecture
- **Frontend:** Next.js, React, TypeScript, Tailwind CSS
- **Backend:** Python, Django, Django REST Framework
- **Database:** PostgreSQL

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 14+ (or use the portable setup script `scripts/dev-db.ps1`)

### Backend Setup
1. `cd backend`
2. `python -m venv .venv`
3. `.\.venv\Scripts\Activate.ps1` (Windows)
4. `pip install -r requirements.txt`
5. `python manage.py migrate`
6. `python manage.py init_roles` (Initialize default RBAC roles)
7. `python manage.py runserver`

### Frontend Setup
1. `cd frontend`
2. `npm install`
3. `npm run dev`

Access the application at `http://localhost:3000`.

## Documentation
See the `docs/` directory for detailed architecture, database, API, and product specifications.

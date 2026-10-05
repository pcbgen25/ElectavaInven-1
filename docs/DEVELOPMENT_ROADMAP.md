# Development Roadmap: Electava Inventory

## Phase 1: Core Foundation & Master Data (✅ COMPLETED)
- System Architecture setup (Next.js + Django + PostgreSQL)
- Auth & Role-Based Access Control (RBAC)
- Component Master Database (CRUD, Categories, Manufacturers, Packages)
- Dynamic Specifications Architecture (EAV variant)
- File Uploads (Images & Datasheets)
- Audit Logging
- Frontend generic data tables, UI primitives, PWA setup.

## Phase 2: BOM & Project Management (⏳ NEXT)
- **Projects:** Project creation, tracking, team assignments.
- **BOM Management:** BOM creation, immutable release revisions (REV A, REV B).
- **KiCad Import:** Robust CSV parsing, column mapping, fuzzy component matching.
- **BOM Comparison:** Diff tool for revisions (added, removed, quantity changed).

## Phase 3: Inventory Management
- Multi-level warehouse locations (Room -> Cabinet -> Bin).
- Stock levels (reserved vs available).
- Transaction engine (RECEIVE, ISSUE, TRANSFER) - strictly auditable, no silent changes.

## Phase 4: Suppliers & Purchasing
- Supplier database, Supplier Parts.
- Historical pricing engine.
- Purchase Requests (PR) & Purchase Orders (PO).
- Goods Receiving matching PO to Inventory.

## Phase 5: Advanced Features & Refinement
- Reports and Analytics dashboards.
- Notifications & Alerts (Low stock).
- Mobile optimization & barcode/QR scanning.

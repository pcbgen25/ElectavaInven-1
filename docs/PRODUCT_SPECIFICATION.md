# Product Specification: Electava Inventory

## 1. Product Vision
A real production-ready internal Electronics Engineering Management System. The application will be used internally by an electronics/PCB engineering company to manage components, BOMs, projects, inventory, suppliers, and purchasing.

## 2. Core Modules
1. **Component Database:** Master data for components (Internal PN, MPN, Descriptions).
2. **Dynamic Specifications:** Category-specific attributes (e.g., Capacitance, Resistance).
3. **Suppliers & Pricing:** Multiple suppliers per part with historical pricing.
4. **Projects & BOMs:** Project association, immutable BOM revisions, KiCad CSV import, diff comparison.
5. **Inventory:** Multi-tier storage locations (Warehouse -> Room -> Cabinet -> Drawer), stock transactions.
6. **Purchasing:** Purchase requests, orders, and receiving.
7. **Document Management:** Storage of datasheets and project docs on S3/local.
8. **Administration:** Granular RBAC, audit logs, users.

## 3. User Roles & Permissions
System utilizes a granular RBAC (Role-Based Access Control) system. 
- **SUPER_ADMIN**: Full system access
- **ADMIN**: System administration, user management
- **HARDWARE_ENGINEER / PCB_ENGINEER**: Component & BOM creation/editing
- **PURCHASE / STORE / PRODUCTION**: Procurement, inventory adjustments, and view-only roles.

## 4. Design Tenets
- Modular monolith architecture.
- Source of truth for business logic and authorization lives entirely in the backend.
- Full auditability for critical actions (BOM releases, stock adjustments, pricing changes).

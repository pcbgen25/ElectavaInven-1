# Database Architecture: Electava Inventory

## 1. Overview
The database uses PostgreSQL and is managed via Django's ORM. It strictly separates relational data from blob/file storage (datasheets/images).

## 2. Core Schema Groups

### Accounts & Auth
- `User`: Custom user model (email-based).
- `Role` & `Permission`: RBAC mapping. `User` <-> `Role` <-> `Permission`.

### Components Master Data
- `Component`: Master records (id, internal_pn, mpn, name, description, etc.).
- `Category`: Hierarchical taxonomy (e.g., Passives -> Capacitors).
- `Manufacturer` & `Package`: Linked entities for standardizing names.
- `ComponentAlias`: Alternate part numbers or recognized aliases.

### Dynamic Specifications (EAV Pattern variant)
- `SpecificationDefinition`: Bound to a `Category` (e.g., Capacitance, Voltage). Defines data type (string, integer, decimal) and unit.
- `ComponentSpecification`: The actual values assigned to a `Component` for a given `SpecificationDefinition`.

### Audit & History
- `AuditLog`: Tracks changes (CREATE, UPDATE, DELETE) to sensitive models. Includes user, timestamp, IP, and serialized changes.

### Future Modules (Schema placeholders)
- **Projects & BOMs:** `Project`, `BOM`, `BOMRevision` (immutable), `BOMItem`.
- **Inventory:** `Warehouse`, `Location`, `InventoryItem`, `StockTransaction`.
- **Purchasing:** `Supplier`, `SupplierPart`, `PurchaseOrder`.

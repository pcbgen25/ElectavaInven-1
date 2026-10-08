"""Canonical permission catalog and default role grants.

Synced into the database after every ``migrate`` (see ``services.sync_rbac_catalog``).
Sync adds missing permissions/roles; it never removes grants an admin added at runtime.
Permissions for later phases are declared now so roles can be configured up-front;
holding a permission for an unimplemented module grants nothing until that module exists.
"""

PERMISSIONS: list[tuple[str, str, str]] = [
    # code, name, module
    ("component.view", "View components", "components"),
    ("component.create", "Create components", "components"),
    ("component.edit", "Edit components", "components"),
    ("component.delete", "Delete components", "components"),
    ("masterdata.manage", "Manage categories, packages, manufacturers and specification definitions", "components"),
    ("project.view", "View projects", "projects"),
    ("project.create", "Create projects", "projects"),
    ("project.edit", "Edit projects", "projects"),
    ("project.delete", "Delete projects", "projects"),
    ("project.manage_members", "Add and remove project members", "projects"),
    ("bom.view", "View BOMs", "bom"),
    ("bom.create", "Create BOMs", "bom"),
    ("bom.edit", "Edit BOMs", "bom"),
    ("bom.delete", "Delete BOMs", "bom"),
    ("bom.import", "Import BOMs", "bom"),
    ("bom.release", "Release BOM revisions", "bom"),
    ("inventory.view", "View inventory", "inventory"),
    ("inventory.manage", "Configure stock levels (minimum / reorder)", "inventory"),
    ("inventory.receive", "Receive stock", "inventory"),
    ("inventory.issue", "Issue stock", "inventory"),
    ("inventory.transfer", "Transfer stock", "inventory"),
    ("inventory.adjust", "Adjust stock", "inventory"),
    ("inventory.reserve", "Reserve and release stock", "inventory"),
    ("inventory.transaction_view", "View the stock transaction ledger", "inventory"),
    ("inventory.warehouse_manage", "Manage warehouses and locations", "inventory"),
    ("supplier.view", "View suppliers", "suppliers"),
    ("supplier.create", "Create suppliers", "suppliers"),
    ("supplier.edit", "Edit suppliers and pricing", "suppliers"),
    ("supplier.delete", "Delete suppliers", "suppliers"),
    ("purchase.view", "View purchasing", "purchasing"),
    ("purchase.create", "Create purchase requests", "purchasing"),
    ("purchase.approve", "Approve purchase requests", "purchasing"),
    ("purchase.order", "Create and send purchase orders", "purchasing"),
    ("purchase.receive", "Receive goods", "purchasing"),
    ("document.view", "View documents", "documents"),
    ("document.upload", "Upload documents", "documents"),
    ("document.delete", "Delete documents", "documents"),
    ("report.view", "View reports", "reports"),
    ("report.export", "Export reports", "reports"),
    ("audit.view", "View audit logs", "audit"),
    ("user.manage", "Manage users", "accounts"),
    ("role.manage", "Manage roles and permissions", "accounts"),
    ("settings.manage", "Manage system settings", "accounts"),
]

ALL = "__all__"

_VIEW_ALL = [code for code, _, _ in PERMISSIONS if code.endswith(".view") and code != "audit.view"]

ROLES: dict[str, dict] = {
    "SUPER_ADMIN": {
        "name": "Super Admin",
        "description": "Full access including granting Super Admin.",
        "permissions": ALL,
    },
    "ADMIN": {
        "name": "Admin",
        "description": "Full operational access and user management.",
        "permissions": [c for c, _, _ in PERMISSIONS],
    },
    "HARDWARE_ENGINEER": {
        "name": "Hardware Engineer",
        "description": "Designs circuits, maintains components and BOMs.",
        "permissions": _VIEW_ALL
        + [
            "component.create", "component.edit", "masterdata.manage",
            "project.create", "project.edit", "project.manage_members",
            "bom.create", "bom.edit", "bom.import", "bom.release",
            "inventory.reserve", "inventory.transaction_view",
            "purchase.create", "document.upload", "report.export",
        ],
    },
    "PCB_ENGINEER": {
        "name": "PCB Engineer",
        "description": "PCB layout; maintains footprints/packages, components and BOMs.",
        "permissions": _VIEW_ALL
        + [
            "component.create", "component.edit", "masterdata.manage",
            "bom.create", "bom.edit", "bom.import",
            "document.upload", "report.export",
        ],
    },
    "PURCHASE": {
        "name": "Purchase",
        "description": "Suppliers, pricing, purchase requests and orders.",
        "permissions": _VIEW_ALL
        + [
            "supplier.create", "supplier.edit",
            "purchase.create", "purchase.order",
            "inventory.transaction_view",
            "document.upload", "report.export",
        ],
    },
    "STORE": {
        "name": "Store",
        "description": "Stock receiving, issuing, transfers and locations.",
        "permissions": _VIEW_ALL
        + [
            "inventory.receive", "inventory.issue", "inventory.transfer", "inventory.adjust",
            "inventory.reserve", "inventory.manage", "inventory.transaction_view",
            "inventory.warehouse_manage", "purchase.receive", "report.export",
        ],
    },
    "PRODUCTION": {
        "name": "Production",
        "description": "Consumes stock against projects and BOMs.",
        "permissions": [
            "component.view", "project.view", "bom.view", "inventory.view",
            "inventory.issue", "inventory.transaction_view", "document.view", "report.view",
        ],
    },
    "VIEWER": {
        "name": "Viewer",
        "description": "Read-only access.",
        "permissions": _VIEW_ALL,
    },
}

SUPER_ADMIN = "SUPER_ADMIN"

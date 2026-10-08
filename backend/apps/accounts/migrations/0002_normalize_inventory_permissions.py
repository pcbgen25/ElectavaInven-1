"""Normalize inventory/project permission codes on existing databases.

``sync_rbac_catalog`` only grants defaults to roles when they are first created, so permissions
introduced after a role exists must be granted here, once. Admin-customised grants are preserved:
nothing is revoked, and the renamed permission keeps every role that already held it.
"""
from django.db import migrations

RENAMES = {"inventory.manage_locations": ("inventory.warehouse_manage", "Manage warehouses and locations")}

NEW_PERMISSIONS = {
    "inventory.manage": ("Configure stock levels (minimum / reorder)", "inventory"),
    "inventory.transaction_view": ("View the stock transaction ledger", "inventory"),
    "inventory.warehouse_manage": ("Manage warehouses and locations", "inventory"),
    "project.manage_members": ("Add and remove project members", "projects"),
    "bom.delete": ("Delete BOMs", "bom"),
}

# Frozen copy of the default grants for the new codes (rbac_catalog may change later).
GRANTS = {
    "ADMIN": ["inventory.manage", "inventory.transaction_view", "inventory.warehouse_manage", "project.manage_members", "bom.delete"],
    "STORE": ["inventory.manage", "inventory.transaction_view", "inventory.warehouse_manage"],
    "PRODUCTION": ["inventory.transaction_view"],
    "PURCHASE": ["inventory.transaction_view"],
    "HARDWARE_ENGINEER": ["inventory.transaction_view", "project.manage_members"],
}


def forwards(apps, schema_editor):
    Permission = apps.get_model("accounts", "Permission")
    Role = apps.get_model("accounts", "Role")

    for old, (new, name) in RENAMES.items():
        old_perm = Permission.objects.filter(code=old).first()
        if old_perm is None:
            continue
        new_perm = Permission.objects.filter(code=new).first()
        if new_perm is None:
            old_perm.code, old_perm.name = new, name
            old_perm.save(update_fields=["code", "name"])
        else:
            for role in Role.objects.filter(permissions=old_perm):
                role.permissions.add(new_perm)
            old_perm.delete()

    for code, (name, module) in NEW_PERMISSIONS.items():
        Permission.objects.get_or_create(code=code, defaults={"name": name, "module": module})

    for role_code, codes in GRANTS.items():
        role = Role.objects.filter(code=role_code).first()
        if role is not None:
            role.permissions.add(*Permission.objects.filter(code__in=codes))


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]

import re

with open('config/settings/base.py', 'r') as f:
    settings = f.read()
if 'apps.inventory' not in settings:
    settings = settings.replace("'apps.bom',", "'apps.bom',\n    'apps.inventory',")
    with open('config/settings/base.py', 'w') as f:
        f.write(settings)

with open('config/urls.py', 'r') as f:
    urls = f.read()
if 'api/inventory/' not in urls:
    urls = urls.replace("path('api/boms/', include('apps.bom.urls')),", "path('api/boms/', include('apps.bom.urls')),\n    path('api/inventory/', include('apps.inventory.urls')),")
    with open('config/urls.py', 'w') as f:
        f.write(urls)

with open('apps/accounts/rbac_catalog.py', 'r') as f:
    rbac = f.read()
if 'inventory.view' not in rbac:
    inventory_perms = """
    'inventory.view': 'View inventory and stock levels',
    'inventory.manage': 'Manage warehouses and locations',
    'inventory.receive': 'Receive stock into inventory',
    'inventory.issue': 'Issue stock from inventory',
    'inventory.adjust': 'Adjust stock quantities',
    'inventory.transfer': 'Transfer stock between locations',
    'inventory.reserve': 'Reserve and release stock',
    'inventory.transaction_view': 'View stock transaction history',
"""
    rbac = rbac.replace("'bom.export': 'Export BOM data',", "'bom.export': 'Export BOM data'," + inventory_perms)
    with open('apps/accounts/rbac_catalog.py', 'w') as f:
        f.write(rbac)

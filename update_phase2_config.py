import os

# Update config/urls.py
urls_path = 'backend/config/urls.py'
with open(urls_path, 'r') as f:
    urls_content = f.read()

if 'apps.projects.urls' not in urls_content:
    urls_content = urls_content.replace(
        "path('api/', include('apps.manufacturers.urls')),",
        "path('api/', include('apps.manufacturers.urls')),\n    path('api/', include('apps.projects.urls')),\n    path('api/', include('apps.bom.urls')),"
    )
    with open(urls_path, 'w') as f:
        f.write(urls_content)


# Update apps/accounts/rbac_catalog.py
rbac_path = 'backend/apps/accounts/rbac_catalog.py'
with open(rbac_path, 'r') as f:
    rbac_content = f.read()

permissions_to_add = """    # Phase 2: Projects
    "project.view": "Can view projects",
    "project.create": "Can create projects",
    "project.edit": "Can edit projects",
    "project.delete": "Can delete projects",
    "project.manage_members": "Can manage project members",

    # Phase 2: BOM
    "bom.view": "Can view BOMs",
    "bom.create": "Can create BOMs",
    "bom.edit": "Can edit BOMs",
    "bom.import": "Can import BOMs",
    "bom.review": "Can review BOMs",
    "bom.release": "Can release BOMs",
    "bom.compare": "Can compare BOM revisions",
"""

if '"project.view"' not in rbac_content:
    rbac_content = rbac_content.replace(
        '# Reports',
        f'{permissions_to_add}\n    # Reports'
    )
    # Also add to default admin roles if desired
    rbac_content = rbac_content.replace(
        '"component.delete",',
        '"component.delete",\n            "project.view",\n            "project.create",\n            "project.edit",\n            "project.delete",\n            "project.manage_members",\n            "bom.view",\n            "bom.create",\n            "bom.edit",\n            "bom.import",\n            "bom.review",\n            "bom.release",\n            "bom.compare",'
    )
    
    with open(rbac_path, 'w') as f:
        f.write(rbac_content)

print("Updated urls and permissions.")

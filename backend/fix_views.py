import os, glob

for filepath in glob.glob('apps/*/views.py'):
    with open(filepath, 'r') as f:
        c = f.read()
    
    # Fix ProjectViewSet
    if "project.view" in c and '"GET"' in c:
        c = c.replace('"GET": "project.view",', '"list": "project.view",\n        "retrieve": "project.view",')
        c = c.replace('"POST": "project.create",', '"create": "project.create",')
        c = c.replace('"PUT": "project.edit",', '"update": "project.edit",')
        c = c.replace('"PATCH": "project.edit",', '"partial_update": "project.edit",')
        c = c.replace('"DELETE": "project.delete"', '"destroy": "project.delete"')

    # Fix BOMViewSet, BOMRevisionViewSet, BOMItemViewSet
    if "bom.view" in c and '"GET"' in c:
        c = c.replace('"GET": "bom.view",', '"list": "bom.view",\n        "retrieve": "bom.view",')
        c = c.replace('"POST": "bom.create",', '"create": "bom.create",')
        c = c.replace('"PUT": "bom.edit",', '"update": "bom.edit",')
        c = c.replace('"PATCH": "bom.edit",', '"partial_update": "bom.edit",')
        c = c.replace('"DELETE": "bom.delete"', '"destroy": "bom.delete"')
        
        c = c.replace('"POST": "bom.edit",', '"create": "bom.edit",')

    with open(filepath, 'w') as f:
        f.write(c)

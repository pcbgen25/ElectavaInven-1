with open('config/settings/base.py', 'r') as f:
    settings = f.read()
if '"apps.inventory"' not in settings:
    settings = settings.replace('"apps.bom",', '"apps.bom",\n    "apps.inventory",')
    with open('config/settings/base.py', 'w') as f:
        f.write(settings)

with open('config/urls.py', 'r') as f:
    urls = f.read()
if '"apps.inventory.urls"' not in urls:
    urls = urls.replace('path("", include("apps.bom.urls")),', 'path("", include("apps.bom.urls")),\n    path("api/inventory/", include("apps.inventory.urls")),')
    with open('config/urls.py', 'w') as f:
        f.write(urls)

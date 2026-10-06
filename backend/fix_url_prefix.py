with open('config/urls.py', 'r') as f:
    urls = f.read()

urls = urls.replace('path("api/inventory/", include("apps.inventory.urls"))', 'path("inventory/", include("apps.inventory.urls"))')

with open('config/urls.py', 'w') as f:
    f.write(urls)

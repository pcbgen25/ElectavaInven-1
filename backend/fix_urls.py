with open('config/urls.py', 'r') as f:
    c = f.read()
if 'apps.projects.urls' not in c:
    c = c.replace('path("", include("apps.manufacturers.urls")),', 'path("", include("apps.manufacturers.urls")),\n    path("", include("apps.projects.urls")),\n    path("", include("apps.bom.urls")),')
    with open('config/urls.py', 'w') as f:
        f.write(c)

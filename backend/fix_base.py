with open('config/settings/base.py', 'r') as f:
    content = f.read()
if '"apps.projects"' not in content:
    content = content.replace('"apps.manufacturers",', '"apps.manufacturers",\n    "apps.projects",\n    "apps.bom",')
    with open('config/settings/base.py', 'w') as f:
        f.write(content)

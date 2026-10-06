with open('apps/core/permissions.py', 'r') as f:
    c = f.read()

c = c.replace(
'''    mapping = getattr(view, "required_permissions", None)
    if mapping is None:
        return None
    action = getattr(view, "action", None) or request.method.lower()''',
'''    mapping = getattr(view, "required_permissions", None)
    if mapping is None:
        return None
    if isinstance(mapping, (str, list)):
        return mapping
    action = getattr(view, "action", None) or request.method.lower()'''
)

with open('apps/core/permissions.py', 'w') as f:
    f.write(c)

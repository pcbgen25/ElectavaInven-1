with open('apps/inventory/views.py', 'r') as f:
    v = f.read()
v = v.replace('BaseRBACPermission', 'HasRBACPermission')
with open('apps/inventory/views.py', 'w') as f:
    f.write(v)

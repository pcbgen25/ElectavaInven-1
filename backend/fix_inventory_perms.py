import re

with open('apps/inventory/services.py', 'r') as f:
    s = f.read()

s = s.replace('entity=item,', '')

with open('apps/inventory/services.py', 'w') as f:
    f.write(s)


with open('apps/inventory/views.py', 'r') as f:
    v = f.read()

v = v.replace("""    required_permissions = {
        'GET': 'inventory.view',
        'POST': 'inventory.manage',
        'PUT': 'inventory.manage',
        'PATCH': 'inventory.manage',
        'DELETE': 'inventory.manage',
    }""", """    required_permissions = {
        'list': 'inventory.view',
        'retrieve': 'inventory.view',
        'create': 'inventory.manage',
        'update': 'inventory.manage',
        'partial_update': 'inventory.manage',
        'destroy': 'inventory.manage',
    }""")

v = v.replace("""    required_permissions = {'GET': 'inventory.view'}""", """    required_permissions = {'list': 'inventory.view', 'retrieve': 'inventory.view', '*': 'inventory.view'}""")
v = v.replace("""    required_permissions = {'GET': 'inventory.transaction_view'}""", """    required_permissions = {'list': 'inventory.transaction_view', 'retrieve': 'inventory.transaction_view', '*': 'inventory.transaction_view'}""")

v = v.replace("""required_permissions={'POST': 'inventory.receive'}""", """required_permissions='inventory.receive'""")
v = v.replace("""required_permissions={'POST': 'inventory.issue'}""", """required_permissions='inventory.issue'""")
v = v.replace("""required_permissions={'POST': 'inventory.adjust'}""", """required_permissions='inventory.adjust'""")
v = v.replace("""required_permissions={'POST': 'inventory.transfer'}""", """required_permissions='inventory.transfer'""")
v = v.replace("""required_permissions={'POST': 'inventory.reserve'}""", """required_permissions='inventory.reserve'""")


with open('apps/inventory/views.py', 'w') as f:
    f.write(v)


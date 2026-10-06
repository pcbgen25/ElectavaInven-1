with open('apps/inventory/serializers.py', 'r') as f:
    s = f.read()
s = s.replace('from apps.components.serializers import ComponentSerializer', 'from apps.components.serializers import ComponentListSerializer')
with open('apps/inventory/serializers.py', 'w') as f:
    f.write(s)

with open('apps/inventory/tests/test_inventory.py', 'r') as f:
    t = f.read()
t = t.replace('User.objects.create_superuser(username="admin", password="password")', 'User.objects.create_superuser(username="admin", email="admin@test.com", password="password")')
with open('apps/inventory/tests/test_inventory.py', 'w') as f:
    f.write(t)

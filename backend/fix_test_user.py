with open('apps/inventory/tests/test_inventory.py', 'r') as f:
    t = f.read()
t = t.replace('User.objects.create_superuser(username="admin", email="admin@test.com", password="password")', 'User.objects.create_superuser(email="admin@test.com", password="password", first_name="admin", last_name="admin")')
with open('apps/inventory/tests/test_inventory.py', 'w') as f:
    f.write(t)

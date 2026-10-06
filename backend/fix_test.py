with open('apps/inventory/tests/test_inventory.py', 'r') as f:
    t = f.read()

t = t.replace("'warehouse_id': str(test_data['wh'].id),", "'warehouse_id': str(test_data['wh'].id),\n            'location_id': str(test_data['loc'].id),")

with open('apps/inventory/tests/test_inventory.py', 'w') as f:
    f.write(t)

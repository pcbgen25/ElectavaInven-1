with open('apps/inventory/services.py', 'r') as f:
    s = f.read()

s = s.replace("""    out_txn.reference_id = f"IN-{in_txn.id}"
    in_txn.reference_id = f"OUT-{out_txn.id}"
    out_txn.save(update_fields=['reference_id'])
    in_txn.save(update_fields=['reference_id'])""", """    StockTransaction.objects.filter(pk=out_txn.pk).update(reference_id=f"IN-{in_txn.id}")
    StockTransaction.objects.filter(pk=in_txn.pk).update(reference_id=f"OUT-{out_txn.id}")""")

with open('apps/inventory/services.py', 'w') as f:
    f.write(s)


with open('apps/inventory/tests/test_inventory.py', 'r') as f:
    t = f.read()

t = t.replace("""        res = client.post('/api/inventory/operations/reserve/', {
            'component_id': str(test_data['comp'].id),
            'warehouse_id': str(test_data['wh'].id),
            'quantity': 30
        })""", """        res = client.post('/api/inventory/operations/reserve/', {
            'component_id': str(test_data['comp'].id),
            'warehouse_id': str(test_data['wh'].id),
            'location_id': str(test_data['loc'].id),
            'quantity': 30
        })""")

with open('apps/inventory/tests/test_inventory.py', 'w') as f:
    f.write(t)

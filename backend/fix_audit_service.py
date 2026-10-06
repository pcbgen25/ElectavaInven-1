with open('apps/inventory/services.py', 'r') as f:
    s = f.read()

s = s.replace('from apps.audit.services import AuditLogger', 'from apps.audit.services import record')
s = s.replace('AuditLogger.log(', 'record(')
s = s.replace('user=user,', 'user=user, entity_type="inventoryitem", entity_id=item.id, entity_repr=str(item),')

with open('apps/inventory/services.py', 'w') as f:
    f.write(s)

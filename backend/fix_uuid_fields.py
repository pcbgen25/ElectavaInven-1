with open('apps/inventory/serializers.py', 'r') as f:
    s = f.read()

s = s.replace('serializers.UUIDField(', 'serializers.IntegerField(')

with open('apps/inventory/serializers.py', 'w') as f:
    f.write(s)

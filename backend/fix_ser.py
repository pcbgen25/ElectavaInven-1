with open('apps/bom/serializers.py', 'r') as f:
    c = f.read()

c = c.replace('read_only_fields = ["revision"]', 'read_only_fields = []')
c = c.replace('read_only_fields = ["bom", "created_by", "released_by", "released_at"]', 'read_only_fields = ["created_by", "released_by", "released_at"]')

with open('apps/bom/serializers.py', 'w') as f:
    f.write(c)

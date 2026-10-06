with open('apps/bom/serializers.py', 'r') as f:
    c = f.read()

import re
replacement = '''class BOMRevisionSerializer(serializers.ModelSerializer):
    items = BOMItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = BOMRevision
        fields = ["id", "bom", "revision_number", "revision_name", "description", "status", "created_by", "created_at", "released_by", "released_at", "items"]
        read_only_fields = ["created_by", "released_by", "released_at"]

    def validate(self, data):
        if self.instance and self.instance.status == "RELEASED":
            raise serializers.ValidationError("Cannot modify a released BOM revision.")
        return data'''

c = re.sub(r'class BOMRevisionSerializer.*?read_only_fields = \["created_by", "released_by", "released_at"\]', replacement, c, flags=re.DOTALL)
with open('apps/bom/serializers.py', 'w') as f:
    f.write(c)

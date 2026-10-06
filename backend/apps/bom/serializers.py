from rest_framework import serializers
from .models import BOM, BOMRevision, BOMItem
from apps.components.serializers import ComponentListSerializer

class BOMItemSerializer(serializers.ModelSerializer):
    component_details = ComponentListSerializer(source="component", read_only=True)
    
    class Meta:
        model = BOMItem
        fields = ["id", "revision", "component", "component_details", "designators", "quantity", "description", "notes", "unit_cost_snapshot", "total_cost_snapshot"]
        read_only_fields = []

class BOMRevisionSerializer(serializers.ModelSerializer):
    items = BOMItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = BOMRevision
        fields = ["id", "bom", "revision_number", "revision_name", "description", "status", "created_by", "created_at", "released_by", "released_at", "items"]
        read_only_fields = ["created_by", "released_by", "released_at"]

    def validate(self, data):
        if self.instance and self.instance.status == "RELEASED":
            raise serializers.ValidationError("Cannot modify a released BOM revision.")
        return data

class BOMSerializer(serializers.ModelSerializer):
    revisions = BOMRevisionSerializer(many=True, read_only=True)
    
    class Meta:
        model = BOM
        fields = ["id", "project", "name", "description", "status", "created_by", "created_at", "updated_at", "revisions"]
        read_only_fields = ["created_by"]

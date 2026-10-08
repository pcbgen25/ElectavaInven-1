from decimal import Decimal

from rest_framework import serializers

from apps.components.models import Component
from apps.projects.models import Project

from .models import BOM, BOMItem, BOMRevision
from .services import LOCKED_STATUSES


class ComponentBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Component
        fields = ["id", "internal_part_number", "mpn", "name"]


class BOMItemSerializer(serializers.ModelSerializer):
    component = serializers.PrimaryKeyRelatedField(queryset=Component.objects.all())
    component_details = ComponentBriefSerializer(source="component", read_only=True)
    quantity = serializers.DecimalField(max_digits=10, decimal_places=4, min_value=Decimal("0.0001"))
    designators = serializers.ListField(child=serializers.CharField(max_length=50), required=False)

    class Meta:
        model = BOMItem
        fields = [
            "id", "revision", "component", "component_details", "designators", "quantity", "description", "notes",
            "unit_cost_snapshot", "total_cost_snapshot",
        ]
        # Cost snapshots are written by the pricing service (Phase 4), never by clients.
        read_only_fields = ["unit_cost_snapshot", "total_cost_snapshot"]

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None and not isinstance(self.instance, list):
            fields["revision"].read_only = True  # items never move between revisions
        return fields

    def validate_revision(self, revision):
        if revision.status in LOCKED_STATUSES:
            raise serializers.ValidationError("Cannot add items to a released BOM revision. Create a new revision instead.")
        return revision

    def validate_designators(self, value):
        cleaned = [d.strip().upper() for d in value if d.strip()]
        if len(set(cleaned)) != len(cleaned):
            raise serializers.ValidationError("Duplicate reference designators.")
        return cleaned


class BOMRevisionListSerializer(serializers.ModelSerializer):
    item_count = serializers.IntegerField(read_only=True, default=None)

    class Meta:
        model = BOMRevision
        fields = ["id", "bom", "revision_number", "revision_name", "description", "status", "created_at",
                  "released_at", "item_count"]


class BOMRevisionSerializer(serializers.ModelSerializer):
    items = BOMItemSerializer(many=True, read_only=True)
    bom = serializers.PrimaryKeyRelatedField(queryset=BOM.objects.all())
    bom_name = serializers.CharField(source="bom.name", read_only=True)
    project = serializers.IntegerField(source="bom.project_id", read_only=True)
    project_code = serializers.CharField(source="bom.project.code", read_only=True)
    created_by_email = serializers.CharField(source="created_by.email", read_only=True, default=None)
    released_by_email = serializers.CharField(source="released_by.email", read_only=True, default=None)
    is_locked = serializers.BooleanField(read_only=True)

    class Meta:
        model = BOMRevision
        fields = [
            "id", "bom", "bom_name", "project", "project_code", "revision_number", "revision_name", "description",
            "status", "is_locked", "created_by", "created_by_email", "created_at", "released_by", "released_by_email",
            "released_at", "items",
        ]
        # status changes only through dedicated actions (release requires bom.release).
        read_only_fields = ["status", "created_by", "released_by", "released_at"]

    def get_fields(self):
        fields = super().get_fields()
        if self.instance is not None and not isinstance(self.instance, list):
            fields["bom"].read_only = True
        return fields

    def validate(self, data):
        if self.instance and self.instance.status in LOCKED_STATUSES:
            raise serializers.ValidationError("Cannot modify a released BOM revision. Create a new revision instead.")
        return data


class BOMSerializer(serializers.ModelSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    project_code = serializers.CharField(source="project.code", read_only=True)
    project_name = serializers.CharField(source="project.name", read_only=True)
    revisions = BOMRevisionListSerializer(many=True, read_only=True)
    current_revision = serializers.SerializerMethodField()
    created_by_email = serializers.CharField(source="created_by.email", read_only=True, default=None)

    class Meta:
        model = BOM
        fields = [
            "id", "project", "project_code", "project_name", "name", "description", "status", "created_by",
            "created_by_email", "created_at", "updated_at", "revisions", "current_revision",
        ]
        read_only_fields = ["status", "created_by", "created_at", "updated_at"]

    def get_current_revision(self, obj):
        """Latest released revision, otherwise the newest revision."""
        revisions = list(obj.revisions.all())
        released = [r for r in revisions if r.status == BOMRevision.Status.RELEASED]
        pick = max(released, key=lambda r: r.released_at) if released else (revisions[0] if revisions else None)
        return BOMRevisionListSerializer(pick).data if pick else None


class BOMImportPreviewSerializer(serializers.Serializer):
    file = serializers.FileField()
    mapping = serializers.JSONField(required=False, binary=True)

    def validate_file(self, f):
        if not f.name.lower().endswith((".csv", ".txt")):
            raise serializers.ValidationError("Upload a CSV file (.csv).")
        return f

    def validate_mapping(self, value):
        if value in (None, ""):
            return None
        if not isinstance(value, dict) or not all(isinstance(k, str) and (v is None or isinstance(v, str)) for k, v in value.items()):
            raise serializers.ValidationError("Mapping must be an object of field -> column name.")
        return value


class BOMImportRowSerializer(serializers.Serializer):
    component = serializers.PrimaryKeyRelatedField(queryset=Component.objects.all())
    quantity = serializers.DecimalField(max_digits=10, decimal_places=4, min_value=Decimal("0.0001"))
    designators = serializers.ListField(child=serializers.CharField(max_length=50), required=False, default=list)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")


class BOMImportConfirmSerializer(serializers.Serializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all())
    name = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    items = BOMImportRowSerializer(many=True, allow_empty=False)

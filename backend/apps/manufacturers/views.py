from django.db.models import Count, Q
from rest_framework import serializers, viewsets

from apps.audit.mixins import AuditedModelViewSetMixin
from apps.core.exceptions import Conflict
from apps.core.routers import OptionalSlashRouter

from .models import Manufacturer


class ManufacturerSerializer(serializers.ModelSerializer):
    component_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Manufacturer
        fields = [
            "id", "name", "short_name", "website", "country", "notes",
            "component_count", "created_at", "updated_at",
        ]

    def validate_name(self, value: str) -> str:
        value = " ".join(value.split())
        qs = Manufacturer.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A manufacturer with this name already exists.")
        return value


class ManufacturerViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = ManufacturerSerializer
    search_fields = ["name", "short_name", "country"]
    ordering_fields = ["name", "country", "component_count", "created_at"]
    ordering = ["name"]
    required_permissions = {
        "list": "component.view",
        "retrieve": "component.view",
        "create": "masterdata.manage",
        "update": "masterdata.manage",
        "partial_update": "masterdata.manage",
        "destroy": "masterdata.manage",
    }

    def get_queryset(self):
        return Manufacturer.objects.annotate(
            component_count=Count("components", filter=Q(components__deleted_at__isnull=True), distinct=True)
        )

    def perform_update(self, serializer):
        old_name = serializer.instance.name
        super().perform_update(serializer)
        if serializer.instance.name != old_name:
            from apps.components.services import rebuild_search_documents_for

            rebuild_search_documents_for(manufacturer=serializer.instance)

    def check_can_delete(self, instance):
        if instance.components.filter(deleted_at__isnull=True).exists():
            raise Conflict("Manufacturer has components. Reassign or delete them first.")


router = OptionalSlashRouter()
router.register("manufacturers", ManufacturerViewSet, basename="manufacturer")

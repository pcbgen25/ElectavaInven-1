import django_filters
from rest_framework import mixins, serializers, viewsets

from apps.core.routers import OptionalSlashRouter

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = [
            "id",
            "timestamp",
            "user",
            "user_email",
            "action",
            "entity_type",
            "entity_id",
            "entity_repr",
            "old_value",
            "new_value",
            "metadata",
            "ip_address",
        ]


class AuditLogFilter(django_filters.FilterSet):
    timestamp_after = django_filters.IsoDateTimeFilter(field_name="timestamp", lookup_expr="gte")
    timestamp_before = django_filters.IsoDateTimeFilter(field_name="timestamp", lookup_expr="lte")

    class Meta:
        model = AuditLog
        fields = ["action", "entity_type", "entity_id", "user"]


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read-only. Audit logs cannot be created, changed or deleted through the API."""

    queryset = AuditLog.objects.all()
    serializer_class = AuditLogSerializer
    filterset_class = AuditLogFilter
    search_fields = ["entity_repr", "user_email", "entity_id"]
    ordering_fields = ["timestamp", "action", "entity_type"]
    required_permissions = {"list": "audit.view", "retrieve": "audit.view"}


router = OptionalSlashRouter()
router.register("audit-logs", AuditLogViewSet, basename="audit-log")

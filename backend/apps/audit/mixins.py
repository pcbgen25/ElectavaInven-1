"""ViewSet mixin that writes audit entries for create/update and performs soft delete."""
from . import services as audit


class AuditedModelViewSetMixin:
    """Use with ModelViewSet for simple master-data resources.

    Resources with richer business logic should call their module's ``services.py``
    (which records audit itself) instead of relying on this mixin.
    """

    def perform_create(self, serializer):
        user = self.request.user
        extra = {}
        model = serializer.Meta.model
        field_names = {f.name for f in model._meta.fields}
        if "created_by" in field_names:
            extra["created_by"] = user
        if "updated_by" in field_names:
            extra["updated_by"] = user
        instance = serializer.save(**extra)
        audit.record_create(instance, request=self.request)

    def perform_update(self, serializer):
        old = audit.snapshot(serializer.instance)
        extra = {}
        if "updated_by" in {f.name for f in serializer.instance._meta.fields}:
            extra["updated_by"] = self.request.user
        instance = serializer.save(**extra)
        audit.record_update(instance, old, request=self.request)

    def perform_destroy(self, instance):
        self.check_can_delete(instance)
        if hasattr(instance, "soft_delete"):
            instance.soft_delete(self.request.user)
            audit.record_delete(instance, request=self.request, soft=True)
        else:
            audit.record_delete(instance, request=self.request, soft=False)
            instance.delete()

    def check_can_delete(self, instance) -> None:
        """Override to raise Conflict when the record is still in use."""

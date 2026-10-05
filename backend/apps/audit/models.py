from django.conf import settings
from django.db import models


class AuditAction(models.TextChoices):
    CREATE = "CREATE", "Create"
    UPDATE = "UPDATE", "Update"
    DELETE = "DELETE", "Delete"
    RESTORE = "RESTORE", "Restore"
    LOGIN = "LOGIN", "Login"
    LOGOUT = "LOGOUT", "Logout"
    LOGIN_FAILED = "LOGIN_FAILED", "Login failed"
    PASSWORD_CHANGE = "PASSWORD_CHANGE", "Password change"
    PERMISSION_CHANGE = "PERMISSION_CHANGE", "Permission change"
    FILE_UPLOAD = "FILE_UPLOAD", "File upload"
    FILE_DELETE = "FILE_DELETE", "File delete"
    # Reserved for later phases (declared now so the enum is stable):
    STOCK_TRANSACTION = "STOCK_TRANSACTION", "Stock transaction"
    BOM_RELEASE = "BOM_RELEASE", "BOM release"
    BOM_REVISION = "BOM_REVISION", "BOM revision"
    PURCHASE_APPROVAL = "PURCHASE_APPROVAL", "Purchase approval"
    PURCHASE_ORDER = "PURCHASE_ORDER", "Purchase order"


class AuditLogQuerySet(models.QuerySet):
    def update(self, **kwargs):  # pragma: no cover - guard
        raise PermissionError("Audit logs are append-only.")

    def delete(self):  # pragma: no cover - guard
        raise PermissionError("Audit logs are append-only.")


class AuditLog(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_logs"
    )
    user_email = models.CharField(max_length=254, blank=True, help_text="Preserved even if the user is removed.")
    action = models.CharField(max_length=32, choices=AuditAction.choices, db_index=True)
    entity_type = models.CharField(max_length=100, db_index=True, help_text="app_label.model")
    entity_id = models.CharField(max_length=64, blank=True)
    entity_repr = models.CharField(max_length=255, blank=True)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    objects = AuditLogQuerySet.as_manager()

    class Meta:
        ordering = ["-timestamp", "-id"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"], name="audit_entity_idx"),
            models.Index(fields=["user", "-timestamp"], name="audit_user_ts_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.user_email} {self.action} {self.entity_type}#{self.entity_id}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise PermissionError("Audit logs are append-only and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Audit logs are append-only and cannot be deleted.")

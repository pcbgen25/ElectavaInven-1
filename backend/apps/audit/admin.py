from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user_email", "action", "entity_type", "entity_id", "entity_repr")
    list_filter = ("action", "entity_type")
    search_fields = ("user_email", "entity_repr", "entity_id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

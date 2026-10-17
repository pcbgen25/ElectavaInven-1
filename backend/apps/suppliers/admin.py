from django.contrib import admin

from .models import (
    Supplier,
    SupplierContact,
    SupplierPart,
    SupplierPriceBreak,
    SupplierPriceHistory,
)


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "status", "currency", "country", "is_active")
    search_fields = ("code", "name", "legal_name", "email")
    list_filter = ("status", "is_active", "currency")


@admin.register(SupplierContact)
class SupplierContactAdmin(admin.ModelAdmin):
    list_display = ("name", "supplier", "role", "email", "phone", "is_primary")
    search_fields = ("name", "email", "supplier__name")


@admin.register(SupplierPart)
class SupplierPartAdmin(admin.ModelAdmin):
    list_display = ("supplier", "supplier_part_number", "component", "unit_price", "currency", "moq", "is_preferred")
    search_fields = ("supplier_part_number", "component__internal_part_number", "component__mpn")
    list_filter = ("is_preferred", "is_active", "currency")


@admin.register(SupplierPriceBreak)
class SupplierPriceBreakAdmin(admin.ModelAdmin):
    list_display = ("supplier_part", "min_quantity", "unit_price", "currency")


@admin.register(SupplierPriceHistory)
class SupplierPriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("supplier_part", "min_quantity", "unit_price", "currency", "source", "recorded_at")
    readonly_fields = (
        "supplier_part",
        "min_quantity",
        "unit_price",
        "currency",
        "source",
        "reference",
        "recorded_by",
        "recorded_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

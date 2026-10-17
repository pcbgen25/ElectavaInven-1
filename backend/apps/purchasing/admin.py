from django.contrib import admin

from .models import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequest,
    PurchaseRequestItem,
)


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ("request_number", "title", "status", "priority", "project", "created_at")
    search_fields = ("request_number", "title")
    list_filter = ("status", "priority")


@admin.register(PurchaseRequestItem)
class PurchaseRequestItemAdmin(admin.ModelAdmin):
    list_display = ("purchase_request", "component", "quantity", "estimated_unit_price", "currency")


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("po_number", "supplier", "status", "total_amount", "currency", "created_at")
    search_fields = ("po_number", "supplier__name")
    list_filter = ("status", "currency")


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = ("purchase_order", "component", "quantity_ordered", "quantity_received", "unit_price", "line_total")


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "purchase_order", "warehouse", "status", "received_at")
    search_fields = ("receipt_number", "purchase_order__po_number", "supplier_delivery_note")
    list_filter = ("status",)


@admin.register(GoodsReceiptItem)
class GoodsReceiptItemAdmin(admin.ModelAdmin):
    list_display = ("goods_receipt", "component", "warehouse", "location", "quantity_received", "unit_cost_snapshot")

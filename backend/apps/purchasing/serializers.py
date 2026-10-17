"""Serializers for Purchase Requests, Purchase Orders, and Goods Receipts."""
from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.bom.models import BOMRevision
from apps.inventory.models import Warehouse
from apps.suppliers.models import Supplier

from .models import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequest,
    PurchaseRequestItem,
)


def _user_display(user) -> str | None:
    if not user:
        return None
    return user.full_name or user.email


class PurchaseRequestItemSerializer(serializers.ModelSerializer):
    component_internal_part_number = serializers.CharField(source="component.internal_part_number", read_only=True)
    component_mpn = serializers.CharField(source="component.mpn", read_only=True)
    component_name = serializers.CharField(source="component.name", read_only=True)
    preferred_supplier_code = serializers.CharField(source="preferred_supplier.code", read_only=True, default=None)
    preferred_supplier_name = serializers.CharField(source="preferred_supplier.name", read_only=True, default=None)
    supplier_part_number = serializers.CharField(source="supplier_part.supplier_part_number", read_only=True, default=None)

    class Meta:
        model = PurchaseRequestItem
        fields = [
            "id",
            "component",
            "component_internal_part_number",
            "component_mpn",
            "component_name",
            "preferred_supplier",
            "preferred_supplier_code",
            "preferred_supplier_name",
            "supplier_part",
            "supplier_part_number",
            "quantity",
            "estimated_unit_price",
            "currency",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "component_internal_part_number",
            "component_mpn",
            "component_name",
            "preferred_supplier_code",
            "preferred_supplier_name",
            "supplier_part_number",
            "created_at",
            "updated_at",
        ]


class PurchaseRequestSerializer(serializers.ModelSerializer):
    request_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    items = PurchaseRequestItemSerializer(many=True)
    project_code = serializers.CharField(source="project.code", read_only=True, default=None)
    project_name = serializers.CharField(source="project.name", read_only=True, default=None)
    bom_revision_label = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    submitted_by_name = serializers.SerializerMethodField()
    reviewed_by_name = serializers.SerializerMethodField()
    estimated_total = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseRequest
        fields = [
            "id",
            "request_number",
            "title",
            "project",
            "project_code",
            "project_name",
            "bom_revision",
            "bom_revision_label",
            "build_quantity",
            "status",
            "priority",
            "needed_by",
            "notes",
            "submitted_by",
            "submitted_by_name",
            "submitted_at",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "review_notes",
            "item_count",
            "estimated_total",
            "items",
            "created_by",
            "created_by_name",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "project_code",
            "project_name",
            "bom_revision_label",
            "submitted_by",
            "submitted_by_name",
            "submitted_at",
            "reviewed_by",
            "reviewed_by_name",
            "reviewed_at",
            "review_notes",
            "item_count",
            "estimated_total",
            "created_by",
            "created_by_name",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def get_bom_revision_label(self, obj: PurchaseRequest) -> str | None:
        if not obj.bom_revision_id:
            return None
        return f"{obj.bom_revision.bom.name} ({obj.bom_revision.revision_number})"

    def get_created_by_name(self, obj: PurchaseRequest) -> str | None:
        return _user_display(obj.created_by)

    def get_submitted_by_name(self, obj: PurchaseRequest) -> str | None:
        return _user_display(obj.submitted_by)

    def get_reviewed_by_name(self, obj: PurchaseRequest) -> str | None:
        return _user_display(obj.reviewed_by)

    def get_item_count(self, obj: PurchaseRequest) -> int:
        return len(obj.items.all())

    def get_estimated_total(self, obj: PurchaseRequest) -> str:
        total = Decimal("0.0000")
        for item in obj.items.all():
            if item.estimated_unit_price is not None:
                total += (item.quantity * item.estimated_unit_price).quantize(Decimal("0.0001"))
        return str(total.quantize(Decimal("0.0001")))


class BOMShortagePRCreateSerializer(serializers.Serializer):
    bom_revision = serializers.PrimaryKeyRelatedField(queryset=BOMRevision.objects.select_related("bom__project").all())
    build_quantity = serializers.DecimalField(max_digits=14, decimal_places=4, default=Decimal("1.0000"))
    title = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    priority = serializers.ChoiceField(
        choices=PurchaseRequest.Priority.choices,
        default=PurchaseRequest.Priority.NORMAL,
        required=False,
    )
    needed_by = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    apply_moq = serializers.BooleanField(default=False, required=False)


class PRReviewActionSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class ConvertPRToPOSerializer(serializers.Serializer):
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all())
    item_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=False,
    )
    default_warehouse = serializers.PrimaryKeyRelatedField(
        queryset=Warehouse.objects.all(),
        required=False,
        allow_null=True,
    )
    currency = serializers.CharField(max_length=3, required=False, allow_blank=True, default="")
    exchange_rate = serializers.DecimalField(
        max_digits=14,
        decimal_places=6,
        required=False,
        default=Decimal("1.000000"),
    )
    expected_delivery_date = serializers.DateField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    apply_moq = serializers.BooleanField(default=False, required=False)


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    component_internal_part_number = serializers.CharField(source="component.internal_part_number", read_only=True)
    component_mpn = serializers.CharField(source="component.mpn", read_only=True)
    component_name = serializers.CharField(source="component.name", read_only=True)
    unit_price = serializers.DecimalField(max_digits=15, decimal_places=6, required=False, allow_null=True)
    quantity_outstanding = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrderItem
        fields = [
            "id",
            "component",
            "component_internal_part_number",
            "component_mpn",
            "component_name",
            "supplier_part",
            "purchase_request_item",
            "supplier_part_number_snapshot",
            "mpn_snapshot",
            "description_snapshot",
            "quantity_ordered",
            "quantity_received",
            "quantity_outstanding",
            "unit_price",
            "line_total",
            "expected_date",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "component_internal_part_number",
            "component_mpn",
            "component_name",
            "quantity_received",
            "quantity_outstanding",
            "line_total",
            "created_at",
            "updated_at",
        ]

    def get_quantity_outstanding(self, obj: PurchaseOrderItem) -> str:
        return str((obj.quantity_ordered - obj.quantity_received).quantize(Decimal("0.0001")))


class PurchaseOrderSerializer(serializers.ModelSerializer):
    po_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    items = PurchaseOrderItemSerializer(many=True)
    supplier_code = serializers.CharField(source="supplier.code", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    purchase_request_number = serializers.CharField(source="purchase_request.request_number", read_only=True, default=None)
    project_code = serializers.CharField(source="project.code", read_only=True, default=None)
    project_name = serializers.CharField(source="project.name", read_only=True, default=None)
    default_warehouse_code = serializers.CharField(source="default_warehouse.code", read_only=True, default=None)
    default_warehouse_name = serializers.CharField(source="default_warehouse.name", read_only=True, default=None)
    created_by_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()
    sent_by_name = serializers.SerializerMethodField()
    item_count = serializers.SerializerMethodField()

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "po_number",
            "supplier",
            "supplier_code",
            "supplier_name",
            "purchase_request",
            "purchase_request_number",
            "project",
            "project_code",
            "project_name",
            "bom_revision",
            "default_warehouse",
            "default_warehouse_code",
            "default_warehouse_name",
            "status",
            "currency",
            "exchange_rate",
            "subtotal",
            "tax_amount",
            "shipping_amount",
            "discount_amount",
            "total_amount",
            "payment_terms_snapshot",
            "order_date",
            "expected_delivery_date",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "sent_by",
            "sent_by_name",
            "sent_at",
            "notes",
            "item_count",
            "items",
            "created_by",
            "created_by_name",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "supplier_code",
            "supplier_name",
            "purchase_request_number",
            "project_code",
            "project_name",
            "default_warehouse_code",
            "default_warehouse_name",
            "status",
            "subtotal",
            "total_amount",
            "approved_by",
            "approved_by_name",
            "approved_at",
            "sent_by",
            "sent_by_name",
            "sent_at",
            "item_count",
            "created_by",
            "created_by_name",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def get_created_by_name(self, obj: PurchaseOrder) -> str | None:
        return _user_display(obj.created_by)

    def get_approved_by_name(self, obj: PurchaseOrder) -> str | None:
        return _user_display(obj.approved_by)

    def get_sent_by_name(self, obj: PurchaseOrder) -> str | None:
        return _user_display(obj.sent_by)

    def get_item_count(self, obj: PurchaseOrder) -> int:
        return len(obj.items.all())


class GoodsReceiptItemSerializer(serializers.ModelSerializer):
    component_internal_part_number = serializers.CharField(source="component.internal_part_number", read_only=True)
    component_mpn = serializers.CharField(source="component.mpn", read_only=True)
    component_name = serializers.CharField(source="component.name", read_only=True)
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all(), required=False, allow_null=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    location_code = serializers.CharField(source="location.code", read_only=True, default=None)

    class Meta:
        model = GoodsReceiptItem
        fields = [
            "id",
            "purchase_order_item",
            "component",
            "component_internal_part_number",
            "component_mpn",
            "component_name",
            "warehouse",
            "warehouse_code",
            "location",
            "location_code",
            "lot_batch",
            "quantity_received",
            "unit_cost_snapshot",
            "currency_snapshot",
            "exchange_rate_snapshot",
            "stock_transaction",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "component",
            "component_internal_part_number",
            "component_mpn",
            "component_name",
            "warehouse_code",
            "location_code",
            "unit_cost_snapshot",
            "currency_snapshot",
            "exchange_rate_snapshot",
            "stock_transaction",
            "created_at",
            "updated_at",
        ]


class GoodsReceiptSerializer(serializers.ModelSerializer):
    receipt_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    post_immediately = serializers.BooleanField(write_only=True, required=False, default=True)
    items = GoodsReceiptItemSerializer(many=True)
    po_number = serializers.CharField(source="purchase_order.po_number", read_only=True)
    supplier = serializers.IntegerField(source="purchase_order.supplier_id", read_only=True)
    supplier_code = serializers.CharField(source="purchase_order.supplier.code", read_only=True)
    supplier_name = serializers.CharField(source="purchase_order.supplier.name", read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    received_by_name = serializers.SerializerMethodField()

    class Meta:
        model = GoodsReceipt
        fields = [
            "id",
            "receipt_number",
            "purchase_order",
            "po_number",
            "supplier",
            "supplier_code",
            "supplier_name",
            "warehouse",
            "warehouse_code",
            "warehouse_name",
            "status",
            "supplier_delivery_note",
            "idempotency_key",
            "post_immediately",
            "received_by",
            "received_by_name",
            "received_at",
            "notes",
            "items",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "po_number",
            "supplier",
            "supplier_code",
            "supplier_name",
            "warehouse_code",
            "warehouse_name",
            "status",
            "received_by",
            "received_by_name",
            "received_at",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        extra_kwargs = {
            "idempotency_key": {"validators": []},  # Handled in service to return 409 Conflict instead of 400
        }

    def get_received_by_name(self, obj: GoodsReceipt) -> str | None:
        return _user_display(obj.received_by)

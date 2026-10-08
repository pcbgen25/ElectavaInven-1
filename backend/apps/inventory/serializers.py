from decimal import Decimal

from rest_framework import serializers

from apps.bom.models import BOMRevision
from apps.components.models import Component
from apps.projects.models import Project

from .models import QTY, InventoryItem, StockReservation, StockTransaction, Warehouse, WarehouseLocation, compute_stock_status
from .services import InventoryError, positive_quantity


def _user_display(user):
    if user is None:
        return None
    return {"id": user.pk, "email": user.email, "full_name": user.full_name}


class PositiveQuantityField(serializers.Field):
    """Strictly positive, finite Decimal. Rejects 0, negatives, NaN/Infinity, booleans and junk."""

    def to_internal_value(self, data):
        try:
            return positive_quantity(data)
        except InventoryError as exc:
            raise serializers.ValidationError(exc.message_dict.get("quantity", exc.messages)) from None

    def to_representation(self, value):
        return str(value)


class NonNegativeDecimalField(serializers.DecimalField):
    def __init__(self, **kwargs):
        kwargs.setdefault("max_digits", QTY["max_digits"])
        kwargs.setdefault("decimal_places", QTY["decimal_places"])
        kwargs.setdefault("min_value", Decimal("0"))
        super().__init__(**kwargs)


# ----------------------------------------------------------------------------- master data
class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ["id", "code", "name", "description", "address", "is_active", "created_at", "updated_at"]
        read_only_fields = ["created_at", "updated_at"]

    def validate_code(self, value):
        value = value.strip().upper()
        qs = Warehouse.objects.filter(code__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A warehouse with this code already exists.")
        return value


class WarehouseLocationSerializer(serializers.ModelSerializer):
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    parent_location = serializers.PrimaryKeyRelatedField(
        queryset=WarehouseLocation.objects.all(), required=False, allow_null=True
    )
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)

    class Meta:
        model = WarehouseLocation
        fields = [
            "id", "warehouse", "warehouse_code", "code", "name", "description", "location_type",
            "parent_location", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        warehouse = attrs.get("warehouse", getattr(self.instance, "warehouse", None))
        if self.instance and "warehouse" in attrs and attrs["warehouse"].pk != self.instance.warehouse_id:
            if self.instance.inventory_items.exists() or self.instance.stock_transactions.exists():
                raise serializers.ValidationError({"warehouse": "A location with stock history cannot move to another warehouse."})
        if "code" in attrs:
            attrs["code"] = attrs["code"].strip().upper()
        code = attrs.get("code", getattr(self.instance, "code", ""))
        qs = WarehouseLocation.objects.filter(warehouse=warehouse, code__iexact=code)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({"code": "This code already exists in the warehouse."})
        parent = attrs.get("parent_location")
        if parent is not None and parent.warehouse_id != warehouse.pk:
            raise serializers.ValidationError({"parent_location": "Parent location must be in the same warehouse."})
        if parent is not None and self.instance and parent.pk == self.instance.pk:
            raise serializers.ValidationError({"parent_location": "A location cannot be its own parent."})
        return attrs


# ----------------------------------------------------------------------------- stock
class ComponentRefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Component
        fields = ["id", "internal_part_number", "mpn", "name"]


class InventoryItemSerializer(serializers.ModelSerializer):
    component = ComponentRefSerializer(read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    location_code = serializers.CharField(source="location.code", read_only=True, default=None)
    quantity_available = serializers.SerializerMethodField()
    stock_status = serializers.SerializerMethodField()

    class Meta:
        model = InventoryItem
        fields = [
            "id", "component", "warehouse", "warehouse_code", "warehouse_name", "location", "location_code",
            "lot_batch", "quantity_on_hand", "quantity_reserved", "quantity_available", "minimum_stock",
            "reorder_level", "maximum_stock", "unit", "stock_status", "updated_at",
        ]
        read_only_fields = fields

    def get_quantity_available(self, obj) -> str:
        return str(getattr(obj, "available_qty", None) if getattr(obj, "available_qty", None) is not None else obj.quantity_available)

    def get_stock_status(self, obj) -> str:
        return getattr(obj, "stock_status", None) or compute_stock_status(obj.quantity_available, obj.minimum_stock, obj.reorder_level)


class StockLevelsSerializer(serializers.Serializer):
    """The only writable stock fields. Balances can only change through operations."""

    minimum_stock = NonNegativeDecimalField(required=False)
    reorder_level = NonNegativeDecimalField(required=False)
    maximum_stock = NonNegativeDecimalField(required=False, allow_null=True)


class StockTransactionSerializer(serializers.ModelSerializer):
    component = ComponentRefSerializer(read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    location_code = serializers.CharField(source="location.code", read_only=True, default=None)
    performed_by = serializers.SerializerMethodField()

    class Meta:
        model = StockTransaction
        fields = [
            "id", "transaction_type", "component", "warehouse", "warehouse_code", "location", "location_code",
            "lot_batch", "quantity", "quantity_on_hand_after", "quantity_reserved_after", "unit_cost", "currency",
            "source_type", "source_id", "reference", "transfer_group_id", "reason", "notes", "performed_by", "timestamp",
        ]
        read_only_fields = fields

    def get_performed_by(self, obj):
        return _user_display(obj.performed_by)


class StockReservationSerializer(serializers.ModelSerializer):
    component = ComponentRefSerializer(read_only=True)
    warehouse_code = serializers.CharField(source="warehouse.code", read_only=True)
    location_code = serializers.CharField(source="location.code", read_only=True, default=None)
    project_code = serializers.CharField(source="project.code", read_only=True, default=None)
    created_by = serializers.SerializerMethodField()
    released_by = serializers.SerializerMethodField()

    class Meta:
        model = StockReservation
        fields = [
            "id", "inventory_item", "component", "warehouse", "warehouse_code", "location", "location_code", "lot_batch",
            "quantity", "project", "project_code", "bom_revision", "reference_type", "reference_id", "notes", "status",
            "created_by", "created_at", "released_by", "released_at",
        ]
        read_only_fields = fields

    def get_created_by(self, obj):
        return _user_display(obj.created_by)

    def get_released_by(self, obj):
        return _user_display(obj.released_by)


# ----------------------------------------------------------------------------- operation input
class _LocatedSerializer(serializers.Serializer):
    component = serializers.PrimaryKeyRelatedField(queryset=Component.objects.all())
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    location = serializers.PrimaryKeyRelatedField(queryset=WarehouseLocation.objects.all(), required=False, allow_null=True)
    lot_batch = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    quantity = PositiveQuantityField()

    def validate(self, attrs):
        loc = attrs.get("location")
        if loc is not None and loc.warehouse_id != attrs["warehouse"].pk:
            raise serializers.ValidationError({"location": "Location does not belong to the selected warehouse."})
        attrs["lot_batch"] = (attrs.get("lot_batch") or "").strip()
        return attrs


class StockMovementSerializer(_LocatedSerializer):
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")


class StockReceiptSerializer(StockMovementSerializer):
    unit_cost = serializers.DecimalField(max_digits=15, decimal_places=6, min_value=Decimal("0"), required=False, allow_null=True)
    currency = serializers.RegexField(r"^[A-Za-z]{3}$", required=False, allow_blank=True, default="")


class StockAdjustmentSerializer(StockMovementSerializer):
    direction = serializers.ChoiceField(choices=["IN", "OUT"])
    reason = serializers.CharField(max_length=200)

    def validate_reason(self, value):
        if not value.strip():
            raise serializers.ValidationError("A reason is required for stock adjustments.")
        return value.strip()


class StockTransferSerializer(serializers.Serializer):
    component = serializers.PrimaryKeyRelatedField(queryset=Component.objects.all())
    from_warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    from_location = serializers.PrimaryKeyRelatedField(queryset=WarehouseLocation.objects.all(), required=False, allow_null=True)
    to_warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    to_location = serializers.PrimaryKeyRelatedField(queryset=WarehouseLocation.objects.all(), required=False, allow_null=True)
    lot_batch = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    quantity = PositiveQuantityField()
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        for side in ("from", "to"):
            loc = attrs.get(f"{side}_location")
            if loc is not None and loc.warehouse_id != attrs[f"{side}_warehouse"].pk:
                raise serializers.ValidationError({f"{side}_location": "Location does not belong to the selected warehouse."})
        attrs["lot_batch"] = (attrs.get("lot_batch") or "").strip()
        return attrs


class StockReserveSerializer(_LocatedSerializer):
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), required=False, allow_null=True)
    bom_revision = serializers.PrimaryKeyRelatedField(queryset=BOMRevision.objects.all(), required=False, allow_null=True)
    reference_type = serializers.CharField(max_length=50, required=False, allow_blank=True, default="")
    reference_id = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")

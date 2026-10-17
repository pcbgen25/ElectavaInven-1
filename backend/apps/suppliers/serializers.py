"""Serializers for Suppliers, Contacts, SupplierParts, PriceBreaks, and PriceHistory."""
from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from .models import (
    Supplier,
    SupplierContact,
    SupplierPart,
    SupplierPriceBreak,
    SupplierPriceHistory,
)
from .services import generate_supplier_code


class SupplierContactSerializer(serializers.ModelSerializer):
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all(), required=False)

    class Meta:
        model = SupplierContact
        fields = [
            "id",
            "supplier",
            "name",
            "role",
            "email",
            "phone",
            "is_primary",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SupplierSerializer(serializers.ModelSerializer):
    code = serializers.CharField(max_length=50, required=False, allow_blank=True)
    contacts = SupplierContactSerializer(many=True, read_only=True)
    part_count = serializers.IntegerField(read_only=True, default=0)
    purchase_order_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Supplier
        fields = [
            "id",
            "code",
            "name",
            "legal_name",
            "website",
            "email",
            "phone",
            "country",
            "address",
            "currency",
            "payment_terms",
            "tax_id",
            "lead_time_days",
            "rating",
            "status",
            "is_active",
            "notes",
            "part_count",
            "purchase_order_count",
            "contacts",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "part_count",
            "purchase_order_count",
            "contacts",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate_code(self, value: str) -> str:
        value = value.strip().upper()
        if not value:
            return ""
        qs = Supplier.objects.filter(code__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A supplier with this code already exists.")
        return value

    def validate_name(self, value: str) -> str:
        value = " ".join(value.split())
        qs = Supplier.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A supplier with this name already exists.")
        return value

    def validate_currency(self, value: str) -> str:
        value = (value or "USD").strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise serializers.ValidationError("Currency must be a 3-letter ISO code (e.g. USD, EUR, INR).")
        return value

    def validate_rating(self, value):
        if value is not None and not (1 <= value <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value

    def create(self, validated_data):
        if not validated_data.get("code"):
            validated_data["code"] = generate_supplier_code()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "code" in validated_data and not validated_data["code"]:
            validated_data.pop("code")
        return super().update(instance, validated_data)


class SupplierPriceBreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupplierPriceBreak
        fields = ["id", "min_quantity", "unit_price", "currency", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_min_quantity(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("Minimum quantity must be greater than zero.")
        return value

    def validate_unit_price(self, value: Decimal) -> Decimal:
        if value < 0:
            raise serializers.ValidationError("Unit price cannot be negative.")
        return value


class SupplierPriceHistorySerializer(serializers.ModelSerializer):
    recorded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SupplierPriceHistory
        fields = [
            "id",
            "supplier_part",
            "min_quantity",
            "unit_price",
            "currency",
            "source",
            "reference",
            "recorded_by",
            "recorded_by_name",
            "recorded_at",
        ]
        read_only_fields = fields

    def get_recorded_by_name(self, obj) -> str | None:
        if not obj.recorded_by_id:
            return None
        return obj.recorded_by.full_name or obj.recorded_by.email


class SupplierPartSerializer(serializers.ModelSerializer):
    supplier_code = serializers.CharField(source="supplier.code", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    supplier_status = serializers.CharField(source="supplier.status", read_only=True)
    component_internal_part_number = serializers.CharField(source="component.internal_part_number", read_only=True)
    component_mpn = serializers.CharField(source="component.mpn", read_only=True)
    component_name = serializers.CharField(source="component.name", read_only=True)
    price_breaks = SupplierPriceBreakSerializer(many=True, required=False)

    class Meta:
        model = SupplierPart
        fields = [
            "id",
            "supplier",
            "supplier_code",
            "supplier_name",
            "supplier_status",
            "component",
            "component_internal_part_number",
            "component_mpn",
            "component_name",
            "supplier_part_number",
            "manufacturer_part_number",
            "packaging",
            "currency",
            "unit_price",
            "moq",
            "order_multiple",
            "lead_time_days",
            "is_preferred",
            "is_active",
            "product_url",
            "notes",
            "price_breaks",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "supplier_code",
            "supplier_name",
            "supplier_status",
            "component_internal_part_number",
            "component_mpn",
            "component_name",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate_unit_price(self, value: Decimal) -> Decimal:
        if value < 0:
            raise serializers.ValidationError("Unit price cannot be negative.")
        return value

    def validate_moq(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("MOQ must be greater than zero.")
        return value

    def validate_order_multiple(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("Order multiple must be greater than zero.")
        return value

    def validate_currency(self, value: str) -> str:
        value = (value or "USD").strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise serializers.ValidationError("Currency must be a 3-letter ISO code.")
        return value

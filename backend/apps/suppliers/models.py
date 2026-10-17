"""Suppliers, contacts, supplier parts, price breaks, and immutable price history."""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.models import AuthoredModel, SoftDeleteModel, TimeStampedModel

QTY = {"max_digits": 14, "decimal_places": 4}
PRICE = {"max_digits": 15, "decimal_places": 6}


class Supplier(TimeStampedModel, SoftDeleteModel, AuthoredModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        ON_HOLD = "ON_HOLD", "On Hold"
        INACTIVE = "INACTIVE", "Inactive"

    code = models.CharField(max_length=50)
    name = models.CharField(max_length=150)
    legal_name = models.CharField(max_length=200, blank=True)
    website = models.URLField(max_length=300, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    currency = models.CharField(max_length=3, default="USD")
    payment_terms = models.CharField(max_length=100, blank=True)
    tax_id = models.CharField(max_length=100, blank=True)
    lead_time_days = models.PositiveIntegerField(null=True, blank=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(deleted_at__isnull=True),
                name="sup_supplier_code_unique_alive",
            ),
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(deleted_at__isnull=True),
                name="sup_supplier_name_unique_alive",
            ),
            models.CheckConstraint(
                condition=Q(rating__isnull=True) | (Q(rating__gte=1) & Q(rating__lte=5)),
                name="sup_supplier_rating_1_to_5",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class SupplierContact(TimeStampedModel):
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    is_primary = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-is_primary", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.supplier.code})"


class SupplierPart(TimeStampedModel, SoftDeleteModel, AuthoredModel):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="supplier_parts")
    component = models.ForeignKey("components.Component", on_delete=models.PROTECT, related_name="supplier_parts")
    supplier_part_number = models.CharField(max_length=120)
    supplier_part_number_normalized = models.CharField(max_length=120, db_index=True)
    manufacturer_part_number = models.CharField(max_length=120, blank=True)
    packaging = models.CharField(max_length=80, blank=True)
    currency = models.CharField(max_length=3, default="USD")
    unit_price = models.DecimalField(**PRICE, default=Decimal("0.000000"))
    moq = models.DecimalField(**QTY, default=Decimal("1.0000"))
    order_multiple = models.DecimalField(**QTY, default=Decimal("1.0000"))
    lead_time_days = models.PositiveIntegerField(null=True, blank=True)
    is_preferred = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    product_url = models.URLField(max_length=500, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-is_preferred", "supplier__name", "supplier_part_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["supplier", "supplier_part_number_normalized"],
                condition=Q(deleted_at__isnull=True),
                name="sup_part_spn_unique_alive",
            ),
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="sup_part_unit_price_non_negative"),
            models.CheckConstraint(condition=Q(moq__gt=0), name="sup_part_moq_positive"),
            models.CheckConstraint(condition=Q(order_multiple__gt=0), name="sup_part_order_multiple_positive"),
        ]
        indexes = [
            models.Index(fields=["component", "is_active"], name="sup_part_comp_active_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.supplier.code}:{self.supplier_part_number} -> {self.component.internal_part_number}"

    def price_for_quantity(self, quantity: Decimal) -> Decimal:
        """Return effective unit price for ``quantity`` considering quantity price breaks."""
        qty = Decimal(str(quantity))
        breaks = [b for b in self.price_breaks.all() if b.min_quantity <= qty]
        if breaks:
            best = max(breaks, key=lambda b: b.min_quantity)
            return best.unit_price
        return self.unit_price


class SupplierPriceBreak(TimeStampedModel):
    supplier_part = models.ForeignKey(SupplierPart, on_delete=models.CASCADE, related_name="price_breaks")
    min_quantity = models.DecimalField(**QTY)
    unit_price = models.DecimalField(**PRICE)
    currency = models.CharField(max_length=3, default="USD")

    class Meta:
        ordering = ["min_quantity"]
        constraints = [
            models.UniqueConstraint(
                fields=["supplier_part", "min_quantity"],
                name="sup_price_break_unique_qty",
            ),
            models.CheckConstraint(condition=Q(min_quantity__gt=0), name="sup_price_break_qty_positive"),
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="sup_price_break_price_non_negative"),
        ]

    def __str__(self) -> str:
        return f"{self.supplier_part.supplier_part_number} @ {self.min_quantity}+ = {self.unit_price} {self.currency}"


class SupplierPriceHistoryQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Supplier price history records are immutable and cannot be updated.")

    def delete(self):
        raise ValidationError("Supplier price history records are immutable and cannot be deleted.")


class SupplierPriceHistory(models.Model):
    """Append-only record of every price change or quote for a SupplierPart."""

    class Source(models.TextChoices):
        MANUAL = "MANUAL", "Manual entry"
        QUOTE = "QUOTE", "Supplier quote"
        PRICE_BREAK = "PRICE_BREAK", "Price break"
        PURCHASE_ORDER = "PURCHASE_ORDER", "Purchase order"

    supplier_part = models.ForeignKey(SupplierPart, on_delete=models.PROTECT, related_name="price_history")
    min_quantity = models.DecimalField(**QTY, default=Decimal("1.0000"))
    unit_price = models.DecimalField(**PRICE)
    currency = models.CharField(max_length=3, default="USD")
    source = models.CharField(max_length=24, choices=Source.choices, default=Source.MANUAL)
    reference = models.CharField(max_length=100, blank=True, default="")
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="recorded_supplier_prices",
    )
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = SupplierPriceHistoryQuerySet.as_manager()

    class Meta:
        ordering = ["-recorded_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(min_quantity__gt=0), name="sup_price_hist_qty_positive"),
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="sup_price_hist_price_non_negative"),
        ]

    def __str__(self) -> str:
        return f"{self.supplier_part_id} @ {self.min_quantity}: {self.unit_price} {self.currency}"

    def save(self, *args, **kwargs):
        if self.pk is not None and not self._state.adding:
            raise ValidationError("Supplier price history records are immutable and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Supplier price history records are immutable and cannot be deleted.")

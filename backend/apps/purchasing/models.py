"""Purchasing models: PurchaseRequest, PurchaseOrder, GoodsReceipt and line items.

Invariants enforced in both Python and PostgreSQL:
* All quantities and monetary amounts use exact ``Decimal`` types (never float).
* ``PurchaseOrderItem`` enforces ``0 <= quantity_received <= quantity_ordered`` and ``quantity_ordered > 0``.
* Once a ``PurchaseOrder`` leaves ``DRAFT``, its financial terms and line-item quantities/prices are locked;
  only ``quantity_received`` advances via posted ``GoodsReceipt`` rows.
* Once a ``GoodsReceipt`` is ``POSTED``, both the receipt header and its ``GoodsReceiptItem`` rows are
  immutable (enforced by model/queryset guards and a PostgreSQL trigger).
* Creating/approving a ``PurchaseRequest`` or ``PurchaseOrder`` never alters inventory balances;
  stock only changes atomically when a ``GoodsReceipt`` is posted.
"""
from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.core.models import AuthoredModel, SoftDeleteModel, TimeStampedModel

QTY = {"max_digits": 14, "decimal_places": 4}
PRICE = {"max_digits": 15, "decimal_places": 6}
MONEY = {"max_digits": 16, "decimal_places": 4}
RATE = {"max_digits": 14, "decimal_places": 6}


class PurchaseSequence(models.Model):
    prefix = models.CharField(max_length=16, unique=True)
    last_value = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.prefix}:{self.last_value}"


class PurchaseRequest(TimeStampedModel, SoftDeleteModel, AuthoredModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        SUBMITTED = "SUBMITTED", "Submitted"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        ORDERED = "ORDERED", "Ordered"
        CANCELLED = "CANCELLED", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        NORMAL = "NORMAL", "Normal"
        HIGH = "HIGH", "High"
        URGENT = "URGENT", "Urgent"

    request_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=200)
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_requests",
    )
    bom_revision = models.ForeignKey(
        "bom.BOMRevision",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_requests",
    )
    build_quantity = models.DecimalField(**QTY, default=Decimal("1.0000"))
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT, db_index=True)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    needed_by = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="submitted_purchase_requests",
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reviewed_purchase_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(build_quantity__gt=0), name="pr_build_quantity_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.request_number} - {self.title}"


class PurchaseRequestItem(TimeStampedModel):
    purchase_request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name="items")
    component = models.ForeignKey(
        "components.Component",
        on_delete=models.PROTECT,
        related_name="purchase_request_items",
    )
    preferred_supplier = models.ForeignKey(
        "suppliers.Supplier",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_request_items",
    )
    supplier_part = models.ForeignKey(
        "suppliers.SupplierPart",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_request_items",
    )
    quantity = models.DecimalField(**QTY)
    estimated_unit_price = models.DecimalField(**PRICE, null=True, blank=True)
    currency = models.CharField(max_length=3, default="USD")
    notes = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="pr_item_quantity_positive"),
            models.CheckConstraint(
                condition=Q(estimated_unit_price__isnull=True) | Q(estimated_unit_price__gte=0),
                name="pr_item_est_price_non_negative",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.purchase_request.request_number}: {self.component.internal_part_number} x {self.quantity}"

    def _check_editable(self):
        if self.purchase_request_id and self.purchase_request.status not in (
            PurchaseRequest.Status.DRAFT,
            PurchaseRequest.Status.SUBMITTED,
        ):
            raise ValidationError(
                f"Purchase request {self.purchase_request.request_number} is {self.purchase_request.status.lower()} "
                "and its line items cannot be modified."
            )

    def save(self, *args, **kwargs):
        self._check_editable()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._check_editable()
        super().delete(*args, **kwargs)


class PurchaseOrder(TimeStampedModel, SoftDeleteModel, AuthoredModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        APPROVED = "APPROVED", "Approved"
        SENT = "SENT", "Sent to Supplier"
        PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED", "Partially Received"
        RECEIVED = "RECEIVED", "Received"
        CLOSED = "CLOSED", "Closed"
        CANCELLED = "CANCELLED", "Cancelled"

    po_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey("suppliers.Supplier", on_delete=models.PROTECT, related_name="purchase_orders")
    purchase_request = models.ForeignKey(
        PurchaseRequest,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_orders",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_orders",
    )
    bom_revision = models.ForeignKey(
        "bom.BOMRevision",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_orders",
    )
    default_warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_orders",
    )

    status = models.CharField(max_length=24, choices=Status.choices, default=Status.DRAFT, db_index=True)

    # Financial snapshots (all exact Decimal)
    currency = models.CharField(max_length=3, default="USD")
    exchange_rate = models.DecimalField(**RATE, default=Decimal("1.000000"))
    subtotal = models.DecimalField(**MONEY, default=Decimal("0.0000"))
    tax_amount = models.DecimalField(**MONEY, default=Decimal("0.0000"))
    shipping_amount = models.DecimalField(**MONEY, default=Decimal("0.0000"))
    discount_amount = models.DecimalField(**MONEY, default=Decimal("0.0000"))
    total_amount = models.DecimalField(**MONEY, default=Decimal("0.0000"))
    payment_terms_snapshot = models.CharField(max_length=100, blank=True)

    order_date = models.DateField(null=True, blank=True)
    expected_delivery_date = models.DateField(null=True, blank=True)

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_purchase_orders",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sent_purchase_orders",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=Q(exchange_rate__gt=0), name="po_exchange_rate_positive"),
            models.CheckConstraint(condition=Q(subtotal__gte=0), name="po_subtotal_non_negative"),
            models.CheckConstraint(condition=Q(tax_amount__gte=0), name="po_tax_non_negative"),
            models.CheckConstraint(condition=Q(shipping_amount__gte=0), name="po_shipping_non_negative"),
            models.CheckConstraint(condition=Q(discount_amount__gte=0), name="po_discount_non_negative"),
            models.CheckConstraint(condition=Q(total_amount__gte=0), name="po_total_non_negative"),
        ]

    def __str__(self) -> str:
        return f"{self.po_number} ({self.supplier.name})"


class PurchaseOrderItemQuerySet(models.QuerySet):
    def delete(self):
        if self.exclude(purchase_order__status=PurchaseOrder.Status.DRAFT).exists():
            raise ValidationError("Cannot delete items from a non-draft purchase order.")
        return super().delete()


class PurchaseOrderItem(TimeStampedModel):
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name="items")
    component = models.ForeignKey(
        "components.Component",
        on_delete=models.PROTECT,
        related_name="purchase_order_items",
    )
    supplier_part = models.ForeignKey(
        "suppliers.SupplierPart",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="purchase_order_items",
    )
    purchase_request_item = models.ForeignKey(
        PurchaseRequestItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_order_items",
    )

    supplier_part_number_snapshot = models.CharField(max_length=120, blank=True)
    mpn_snapshot = models.CharField(max_length=120, blank=True)
    description_snapshot = models.CharField(max_length=300, blank=True)

    quantity_ordered = models.DecimalField(**QTY)
    quantity_received = models.DecimalField(**QTY, default=Decimal("0.0000"))
    unit_price = models.DecimalField(**PRICE)
    line_total = models.DecimalField(**MONEY)
    expected_date = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=300, blank=True)

    objects = PurchaseOrderItemQuerySet.as_manager()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity_ordered__gt=0), name="po_item_qty_ordered_positive"),
            models.CheckConstraint(condition=Q(quantity_received__gte=0), name="po_item_qty_received_non_negative"),
            models.CheckConstraint(
                condition=Q(quantity_received__lte=F("quantity_ordered")),
                name="po_item_qty_received_lte_ordered",
            ),
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="po_item_unit_price_non_negative"),
            models.CheckConstraint(condition=Q(line_total__gte=0), name="po_item_line_total_non_negative"),
        ]

    @property
    def quantity_outstanding(self) -> Decimal:
        return self.quantity_ordered - self.quantity_received

    def __str__(self) -> str:
        return f"{self.purchase_order.po_number}: {self.component.internal_part_number} ({self.quantity_received}/{self.quantity_ordered})"

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        # Receiving updates only quantity_received and updated_at on approved/sent POs.
        if self.pk is not None and not self._state.adding:
            if update_fields and set(update_fields) <= {"quantity_received", "updated_at"}:
                return super().save(*args, **kwargs)
            if self.purchase_order.status != PurchaseOrder.Status.DRAFT:
                raise ValidationError(
                    f"Purchase order {self.purchase_order.po_number} is {self.purchase_order.status.lower()} "
                    "and its commercial line items are locked."
                )
        else:
            if self.purchase_order_id and self.purchase_order.status != PurchaseOrder.Status.DRAFT:
                raise ValidationError(
                    f"Cannot add items to purchase order {self.purchase_order.po_number} in status {self.purchase_order.status}."
                )
        self.line_total = (Decimal(str(self.quantity_ordered)) * Decimal(str(self.unit_price))).quantize(
            Decimal("0.0001")
        )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.purchase_order.status != PurchaseOrder.Status.DRAFT:
            raise ValidationError(
                f"Cannot delete items from purchase order {self.purchase_order.po_number} in status {self.purchase_order.status}."
            )
        super().delete(*args, **kwargs)


class GoodsReceiptQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if self.filter(status="POSTED").exists():
            raise ValidationError("Posted goods receipts are immutable and cannot be modified.")
        return super().update(**kwargs)

    def delete(self):
        if self.filter(status="POSTED").exists():
            raise ValidationError("Posted goods receipts are immutable and cannot be deleted.")
        return super().delete()


class GoodsReceipt(TimeStampedModel, AuthoredModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        POSTED = "POSTED", "Posted"

    receipt_number = models.CharField(max_length=50, unique=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.PROTECT, related_name="goods_receipts")
    warehouse = models.ForeignKey("inventory.Warehouse", on_delete=models.PROTECT, related_name="goods_receipts")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    supplier_delivery_note = models.CharField(max_length=120, blank=True)
    idempotency_key = models.CharField(max_length=100, unique=True, null=True, blank=True)

    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="posted_goods_receipts",
    )
    received_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    objects = GoodsReceiptQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return f"{self.receipt_number} ({self.purchase_order.po_number})"

    def save(self, *args, **kwargs):
        if self.pk is not None and not self._state.adding:
            prev_status = GoodsReceipt.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if prev_status == self.Status.POSTED:
                raise ValidationError("Posted goods receipts are immutable and cannot be modified.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status == self.Status.POSTED:
            raise ValidationError("Posted goods receipts are immutable and cannot be deleted.")
        super().delete(*args, **kwargs)


class GoodsReceiptItemQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if self.filter(goods_receipt__status=GoodsReceipt.Status.POSTED).exists():
            raise ValidationError("Posted goods receipt items are immutable and cannot be modified.")
        return super().update(**kwargs)

    def delete(self):
        if self.filter(goods_receipt__status=GoodsReceipt.Status.POSTED).exists():
            raise ValidationError("Posted goods receipt items are immutable and cannot be deleted.")
        return super().delete()


class GoodsReceiptItem(TimeStampedModel):
    goods_receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name="items")
    purchase_order_item = models.ForeignKey(
        PurchaseOrderItem,
        on_delete=models.PROTECT,
        related_name="goods_receipt_items",
    )
    component = models.ForeignKey(
        "components.Component",
        on_delete=models.PROTECT,
        related_name="goods_receipt_items",
    )
    warehouse = models.ForeignKey(
        "inventory.Warehouse",
        on_delete=models.PROTECT,
        related_name="goods_receipt_items",
    )
    location = models.ForeignKey(
        "inventory.WarehouseLocation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="goods_receipt_items",
    )
    lot_batch = models.CharField(max_length=100, blank=True, default="")
    quantity_received = models.DecimalField(**QTY)
    unit_cost_snapshot = models.DecimalField(**PRICE)
    currency_snapshot = models.CharField(max_length=3, default="USD")
    exchange_rate_snapshot = models.DecimalField(**RATE, default=Decimal("1.000000"))
    stock_transaction = models.OneToOneField(
        "inventory.StockTransaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="goods_receipt_item",
    )
    notes = models.CharField(max_length=300, blank=True)

    objects = GoodsReceiptItemQuerySet.as_manager()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity_received__gt=0), name="grn_item_qty_received_positive"),
            models.CheckConstraint(condition=Q(unit_cost_snapshot__gte=0), name="grn_item_unit_cost_non_negative"),
            models.CheckConstraint(condition=Q(exchange_rate_snapshot__gt=0), name="grn_item_ex_rate_positive"),
        ]

    def __str__(self) -> str:
        return f"{self.goods_receipt.receipt_number}: {self.component.internal_part_number} +{self.quantity_received}"

    def save(self, *args, **kwargs):
        if self.pk is not None and not self._state.adding:
            # Allow linking stock_transaction during post_goods_receipt BEFORE goods_receipt is marked POSTED.
            if self.goods_receipt.status == GoodsReceipt.Status.POSTED:
                raise ValidationError("Posted goods receipt items are immutable and cannot be modified.")
        else:
            if self.goods_receipt_id and self.goods_receipt.status == GoodsReceipt.Status.POSTED:
                raise ValidationError("Cannot add items to an already posted goods receipt.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.goods_receipt.status == GoodsReceipt.Status.POSTED:
            raise ValidationError("Posted goods receipt items are immutable and cannot be deleted.")
        super().delete(*args, **kwargs)

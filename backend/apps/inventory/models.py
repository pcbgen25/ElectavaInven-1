"""Inventory data model.

Invariants (enforced in the database, not only in Python):

* ``InventoryItem`` identity is (component, warehouse, location, lot_batch). Two partial unique
  constraints cover the NULL-location case, which a plain unique constraint does not in PostgreSQL.
* ``0 <= quantity_reserved <= quantity_on_hand``; therefore ``available = on_hand - reserved >= 0``.
* ``StockTransaction`` rows are append-only. A PostgreSQL trigger (migration 0002) rejects UPDATE and
  DELETE; corrections are made with a compensating transaction.
* Historical rows reference master data with ``PROTECT`` so deleting a warehouse, location, component
  or user can never erase stock history. Warehouses and locations are deactivated (soft deleted).

Sign convention of ``StockTransaction.quantity``: positive = increases the affected balance,
negative = decreases it. RECEIPT/ADJUSTMENT_IN/TRANSFER_IN/RESERVATION are positive;
ISSUE/ADJUSTMENT_OUT/TRANSFER_OUT/RELEASE_RESERVATION are negative. RESERVATION and
RELEASE_RESERVATION change ``quantity_reserved``; all other types change ``quantity_on_hand``.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.core.models import AuthoredModel, SoftDeleteModel, TimeStampedModel

QTY = {"max_digits": 14, "decimal_places": 4}


class Warehouse(TimeStampedModel, SoftDeleteModel):
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        constraints = [
            models.UniqueConstraint(fields=["code"], condition=Q(deleted_at__isnull=True), name="inv_warehouse_code_unique_alive"),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


class WarehouseLocation(TimeStampedModel, SoftDeleteModel):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="locations")
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    location_type = models.CharField(max_length=50, blank=True)
    parent_location = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True, related_name="sub_locations")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["warehouse__code", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["warehouse", "code"], condition=Q(deleted_at__isnull=True), name="inv_location_code_unique_alive"
            ),
        ]

    def __str__(self):
        return f"{self.warehouse.code} / {self.code}"

    def clean(self):
        if self.parent_location_id and self.parent_location.warehouse_id != self.warehouse_id:
            raise ValidationError({"parent_location": "Parent location must be in the same warehouse."})


class StockStatus(models.TextChoices):
    OUT_OF_STOCK = "OUT_OF_STOCK", "Out of stock"
    LOW_STOCK = "LOW_STOCK", "Low stock"
    IN_STOCK = "IN_STOCK", "In stock"


class InventoryItem(TimeStampedModel):
    """Current balance of one component at one warehouse/location/lot. Never deleted."""

    component = models.ForeignKey("components.Component", on_delete=models.PROTECT, related_name="inventory_items")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="inventory_items")
    location = models.ForeignKey(
        WarehouseLocation, on_delete=models.PROTECT, null=True, blank=True, related_name="inventory_items"
    )
    lot_batch = models.CharField(max_length=100, blank=True, default="")

    quantity_on_hand = models.DecimalField(**QTY, default=0)
    quantity_reserved = models.DecimalField(**QTY, default=0)

    minimum_stock = models.DecimalField(**QTY, default=0)
    reorder_level = models.DecimalField(**QTY, default=0)
    maximum_stock = models.DecimalField(**QTY, null=True, blank=True)
    unit = models.CharField(max_length=20, default="pcs")

    class Meta:
        ordering = ["component__internal_part_number", "warehouse__code", "location__code", "lot_batch"]
        constraints = [
            models.UniqueConstraint(
                fields=["component", "warehouse", "location", "lot_batch"],
                condition=Q(location__isnull=False),
                name="inv_item_identity_with_location",
            ),
            models.UniqueConstraint(
                fields=["component", "warehouse", "lot_batch"],
                condition=Q(location__isnull=True),
                name="inv_item_identity_without_location",
            ),
            models.CheckConstraint(condition=Q(quantity_on_hand__gte=0), name="inv_item_on_hand_non_negative"),
            models.CheckConstraint(condition=Q(quantity_reserved__gte=0), name="inv_item_reserved_non_negative"),
            models.CheckConstraint(
                condition=Q(quantity_reserved__lte=F("quantity_on_hand")), name="inv_item_reserved_lte_on_hand"
            ),
            models.CheckConstraint(
                condition=Q(minimum_stock__gte=0) & Q(reorder_level__gte=0), name="inv_item_levels_non_negative"
            ),
        ]
        indexes = [models.Index(fields=["component", "warehouse"], name="inv_item_comp_wh_idx")]

    @property
    def quantity_available(self):
        return self.quantity_on_hand - self.quantity_reserved



    def __str__(self):
        loc = f"/{self.location.code}" if self.location_id else ""
        lot = f" lot {self.lot_batch}" if self.lot_batch else ""
        return f"{self.component.internal_part_number} @ {self.warehouse.code}{loc}{lot}"


def compute_stock_status(available, minimum_stock, reorder_level) -> str:
    """Stock status rule (mirrored by ``services.annotate_stock_status`` in SQL).

    * OUT_OF_STOCK: available <= 0
    * LOW_STOCK:    available <= max(minimum_stock, reorder_level), when that threshold > 0
    * IN_STOCK:     otherwise
    """
    threshold = max(minimum_stock or 0, reorder_level or 0)
    if available <= 0:
        return StockStatus.OUT_OF_STOCK
    if threshold > 0 and available <= threshold:
        return StockStatus.LOW_STOCK
    return StockStatus.IN_STOCK


class StockTransactionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Stock transactions are immutable. Record a compensating transaction instead.")

    def delete(self):
        raise ValidationError("Stock transactions are immutable and cannot be deleted.")


class StockTransaction(models.Model):
    class TransactionType(models.TextChoices):
        RECEIPT = "RECEIPT", "Receipt"
        ISSUE = "ISSUE", "Issue"
        ADJUSTMENT_IN = "ADJUSTMENT_IN", "Adjustment In"
        ADJUSTMENT_OUT = "ADJUSTMENT_OUT", "Adjustment Out"
        TRANSFER_OUT = "TRANSFER_OUT", "Transfer Out"
        TRANSFER_IN = "TRANSFER_IN", "Transfer In"
        RESERVATION = "RESERVATION", "Reservation"
        RELEASE_RESERVATION = "RELEASE_RESERVATION", "Release Reservation"

    class SourceType(models.TextChoices):
        """What created the transaction. Phase 4 will add GOODS_RECEIPT."""

        MANUAL = "MANUAL", "Manual operation"
        TRANSFER = "TRANSFER", "Stock transfer"
        RESERVATION = "RESERVATION", "Stock reservation"
        PROJECT = "PROJECT", "Project"
        BOM_REVISION = "BOM_REVISION", "BOM revision"

    transaction_type = models.CharField(max_length=24, choices=TransactionType.choices)
    component = models.ForeignKey("components.Component", on_delete=models.PROTECT, related_name="stock_transactions")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="stock_transactions")
    location = models.ForeignKey(
        WarehouseLocation, on_delete=models.PROTECT, null=True, blank=True, related_name="stock_transactions"
    )
    lot_batch = models.CharField(max_length=100, blank=True, default="")

    quantity = models.DecimalField(**QTY)
    quantity_on_hand_after = models.DecimalField(**QTY, null=True, blank=True)
    quantity_reserved_after = models.DecimalField(**QTY, null=True, blank=True)

    # Valuation (filled by goods receipts in Phase 4; optional for manual receipts).
    unit_cost = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    currency = models.CharField(max_length=3, blank=True, default="")

    # Source reference: typed origin of the movement.
    source_type = models.CharField(max_length=32, choices=SourceType.choices, default=SourceType.MANUAL)
    source_id = models.CharField(max_length=64, blank=True, default="")
    reference = models.CharField(max_length=100, blank=True, default="", help_text="Free-text document number")
    transfer_group_id = models.UUIDField(null=True, blank=True, db_index=True)

    reason = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, related_name="stock_transactions"
    )
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = StockTransactionQuerySet.as_manager()

    class Meta:
        ordering = ["-timestamp", "-id"]
        constraints = [
            models.CheckConstraint(condition=~Q(quantity=0), name="inv_txn_quantity_non_zero"),
            models.CheckConstraint(
                condition=Q(unit_cost__isnull=True) | Q(unit_cost__gte=0), name="inv_txn_unit_cost_non_negative"
            ),
        ]
        indexes = [
            models.Index(fields=["component", "-timestamp"], name="inv_txn_comp_ts_idx"),
            models.Index(fields=["warehouse", "-timestamp"], name="inv_txn_wh_ts_idx"),
            models.Index(fields=["source_type", "source_id"], name="inv_txn_source_idx"),
            models.Index(fields=["transaction_type", "-timestamp"], name="inv_txn_type_ts_idx"),
        ]

    def __str__(self):
        return f"{self.transaction_type} {self.quantity} {self.component_id}@{self.warehouse_id}"

    def save(self, *args, **kwargs):
        if self.pk is not None and not self._state.adding:
            raise ValidationError("Stock transactions are immutable. Record a compensating transaction instead.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Stock transactions are immutable and cannot be deleted.")


class StockReservation(TimeStampedModel, AuthoredModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        RELEASED = "RELEASED", "Released"
        CANCELLED = "CANCELLED", "Cancelled"

    inventory_item = models.ForeignKey(
        InventoryItem, on_delete=models.PROTECT, null=True, related_name="reservations",
        help_text="The exact stock row reserved against (null only for legacy rows).",
    )
    component = models.ForeignKey("components.Component", on_delete=models.PROTECT, related_name="reservations")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="reservations")
    location = models.ForeignKey(WarehouseLocation, on_delete=models.PROTECT, null=True, blank=True, related_name="reservations")
    lot_batch = models.CharField(max_length=100, blank=True, default="")

    quantity = models.DecimalField(**QTY)

    # Typed references (where practical) plus a generic one for other sources.
    project = models.ForeignKey("projects.Project", on_delete=models.PROTECT, null=True, blank=True, related_name="stock_reservations")
    bom_revision = models.ForeignKey("bom.BOMRevision", on_delete=models.PROTECT, null=True, blank=True, related_name="stock_reservations")
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.CharField(max_length=64, blank=True)
    notes = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    released_at = models.DateTimeField(null=True, blank=True)
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="inv_reservation_quantity_positive"),
        ]
        indexes = [models.Index(fields=["component", "status"], name="inv_res_comp_status_idx")]

    def __str__(self):
        return f"Reservation {self.pk} {self.quantity} x {self.component_id} ({self.status})"

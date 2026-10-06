from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.models import TimeStampedModel, SoftDeleteModel, AuthoredModel

class Warehouse(TimeStampedModel, SoftDeleteModel):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

class WarehouseLocation(TimeStampedModel, SoftDeleteModel):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="locations")
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    location_type = models.CharField(max_length=50, blank=True)
    parent_location = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name="sub_locations")
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = (("warehouse", "code"),)

    def __str__(self):
        return f"{self.warehouse.code} / {self.code}"

class InventoryItem(TimeStampedModel, SoftDeleteModel):
    component = models.ForeignKey('components.Component', on_delete=models.CASCADE, related_name="inventory_items")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="inventory_items")
    location = models.ForeignKey(WarehouseLocation, on_delete=models.SET_NULL, null=True, blank=True, related_name="inventory_items")
    
    quantity_on_hand = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    quantity_reserved = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    
    minimum_stock = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    maximum_stock = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    
    unit = models.CharField(max_length=20, default="pcs")
    lot_batch = models.CharField(max_length=100, blank=True)

    class Meta:
        unique_together = (("component", "warehouse", "location", "lot_batch"),)

    @property
    def quantity_available(self):
        return self.quantity_on_hand - self.quantity_reserved

    def __str__(self):
        return f"{self.component.mpn} @ {self.warehouse.code}"

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

    transaction_type = models.CharField(max_length=20, choices=TransactionType.choices)
    component = models.ForeignKey('components.Component', on_delete=models.CASCADE, related_name="stock_transactions")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    location = models.ForeignKey(WarehouseLocation, on_delete=models.SET_NULL, null=True, blank=True)
    
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.CharField(max_length=50, blank=True)
    reason = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    
    performed_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-timestamp"]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Stock transactions are immutable and cannot be modified.")
        super().save(*args, **kwargs)

class StockReservation(TimeStampedModel, SoftDeleteModel, AuthoredModel):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        RELEASED = "RELEASED", "Released"
        CANCELLED = "CANCELLED", "Cancelled"

    component = models.ForeignKey('components.Component', on_delete=models.CASCADE, related_name="reservations")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    location = models.ForeignKey(WarehouseLocation, on_delete=models.SET_NULL, null=True, blank=True)
    
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    reference_type = models.CharField(max_length=50, blank=True)
    reference_id = models.CharField(max_length=50, blank=True)
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    released_at = models.DateTimeField(null=True, blank=True)

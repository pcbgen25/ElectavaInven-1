import os

app_dir = 'apps/inventory'

models_code = """from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.core.models import BaseModel, AuthoredModel

class Warehouse(BaseModel):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.code} - {self.name}"

class WarehouseLocation(BaseModel):
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

class InventoryItem(BaseModel):
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

class StockReservation(BaseModel, AuthoredModel):
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
"""

services_code = """from django.db import transaction
from django.core.exceptions import ValidationError
from decimal import Decimal
from .models import InventoryItem, StockTransaction, StockReservation, Warehouse, WarehouseLocation
from apps.audit.services import AuditLogger

@transaction.atomic
def execute_stock_operation(transaction_type, component, warehouse, location, quantity, user, reason="", notes="", reference_type="", reference_id="", lot_batch=""):
    quantity = Decimal(str(quantity))
    if quantity < 0 and transaction_type not in (StockTransaction.TransactionType.ADJUSTMENT_OUT, StockTransaction.TransactionType.ISSUE, StockTransaction.TransactionType.TRANSFER_OUT):
        raise ValidationError("Quantity must be positive for this operation.")
        
    item, created = InventoryItem.objects.select_for_update().get_or_create(
        component=component,
        warehouse=warehouse,
        location=location,
        lot_batch=lot_batch,
        defaults={'quantity_on_hand': Decimal('0'), 'quantity_reserved': Decimal('0')}
    )

    if transaction_type in (StockTransaction.TransactionType.RECEIPT, StockTransaction.TransactionType.ADJUSTMENT_IN, StockTransaction.TransactionType.TRANSFER_IN):
        item.quantity_on_hand += quantity
    elif transaction_type in (StockTransaction.TransactionType.ISSUE, StockTransaction.TransactionType.ADJUSTMENT_OUT, StockTransaction.TransactionType.TRANSFER_OUT):
        if item.quantity_available < quantity:
            raise ValidationError(f"Insufficient available stock. Have {item.quantity_available}, required {quantity}.")
        item.quantity_on_hand -= quantity
        quantity = -quantity # record negative in transaction
    elif transaction_type == StockTransaction.TransactionType.RESERVATION:
        if item.quantity_available < quantity:
            raise ValidationError(f"Insufficient available stock for reservation. Have {item.quantity_available}, required {quantity}.")
        item.quantity_reserved += quantity
    elif transaction_type == StockTransaction.TransactionType.RELEASE_RESERVATION:
        if item.quantity_reserved < quantity:
            raise ValidationError("Cannot release more reserved stock than is currently reserved.")
        item.quantity_reserved -= quantity
        quantity = -quantity # record negative in transaction
    else:
        raise ValidationError("Invalid transaction type.")

    item.save()

    txn = StockTransaction.objects.create(
        transaction_type=transaction_type,
        component=component,
        warehouse=warehouse,
        location=location,
        quantity=quantity,
        reference_type=reference_type,
        reference_id=reference_id,
        reason=reason,
        notes=notes,
        performed_by=user
    )

    AuditLogger.log(
        user=user,
        action=f"inventory_{transaction_type.lower()}",
        entity=item,
        new_value={"quantity_change": float(quantity), "new_on_hand": float(item.quantity_on_hand), "new_reserved": float(item.quantity_reserved)},
        metadata={"reason": reason, "reference": f"{reference_type} {reference_id}"}
    )

    return txn, item

@transaction.atomic
def transfer_stock(component, from_warehouse, from_location, to_warehouse, to_location, quantity, user, reason="", lot_batch=""):
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise ValidationError("Transfer quantity must be greater than zero.")

    out_txn, _ = execute_stock_operation(
        StockTransaction.TransactionType.TRANSFER_OUT,
        component, from_warehouse, from_location, quantity, user,
        reason=reason, reference_type="TRANSFER", reference_id="", lot_batch=lot_batch
    )

    in_txn, _ = execute_stock_operation(
        StockTransaction.TransactionType.TRANSFER_IN,
        component, to_warehouse, to_location, quantity, user,
        reason=reason, reference_type="TRANSFER", reference_id="", lot_batch=lot_batch
    )
    
    out_txn.reference_id = f"IN-{in_txn.id}"
    in_txn.reference_id = f"OUT-{out_txn.id}"
    out_txn.save(update_fields=['reference_id'])
    in_txn.save(update_fields=['reference_id'])

    return out_txn, in_txn

@transaction.atomic
def reserve_stock(component, warehouse, location, quantity, user, reference_type="", reference_id="", lot_batch=""):
    quantity = Decimal(str(quantity))
    txn, item = execute_stock_operation(
        StockTransaction.TransactionType.RESERVATION,
        component, warehouse, location, quantity, user,
        reason="Reservation created", reference_type=reference_type, reference_id=reference_id, lot_batch=lot_batch
    )
    
    reservation = StockReservation.objects.create(
        component=component,
        warehouse=warehouse,
        location=location,
        quantity=quantity,
        reference_type=reference_type,
        reference_id=reference_id,
        status=StockReservation.Status.ACTIVE,
        created_by=user
    )
    return reservation

@transaction.atomic
def release_reservation(reservation_id, user):
    reservation = StockReservation.objects.select_for_update().get(id=reservation_id)
    if reservation.status != StockReservation.Status.ACTIVE:
        raise ValidationError("Reservation is not active.")
    
    execute_stock_operation(
        StockTransaction.TransactionType.RELEASE_RESERVATION,
        reservation.component, reservation.warehouse, reservation.location, reservation.quantity, user,
        reason="Reservation released", reference_type=reservation.reference_type, reference_id=reservation.reference_id
    )
    
    reservation.status = StockReservation.Status.RELEASED
    from django.utils import timezone
    reservation.released_at = timezone.now()
    reservation.save()
    return reservation

def get_bom_inventory_availability(bom_revision):
    items = bom_revision.items.all().select_related('component')
    availability = []
    
    from django.db.models import Sum
    from django.db.models.functions import Coalesce

    for item in items:
        # Sum quantities for this component
        stock = InventoryItem.objects.filter(component=item.component).aggregate(
            total_on_hand=Coalesce(Sum('quantity_on_hand'), Decimal('0')),
            total_reserved=Coalesce(Sum('quantity_reserved'), Decimal('0'))
        )
        on_hand = stock['total_on_hand']
        reserved = stock['total_reserved']
        available = on_hand - reserved
        required = item.quantity
        shortage = max(Decimal('0'), required - available)
        
        availability.append({
            'component_id': item.component.id,
            'component_mpn': item.component.mpn,
            'required': required,
            'on_hand': on_hand,
            'reserved': reserved,
            'available': available,
            'shortage': shortage,
            'status': 'SUFFICIENT' if shortage == 0 else 'SHORTAGE'
        })
    return availability
"""

with open(f'{app_dir}/models.py', 'w') as f:
    f.write(models_code)
with open(f'{app_dir}/services.py', 'w') as f:
    f.write(services_code)

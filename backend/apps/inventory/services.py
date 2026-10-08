"""Inventory business operations. The ONLY code path that changes stock balances.

Every operation:
  * validates input server-side (strictly positive, finite Decimal quantities; location belongs to
    the warehouse; active master data),
  * runs inside ``transaction.atomic()``,
  * locks the affected ``InventoryItem`` rows with ``SELECT ... FOR UPDATE`` (rows are created first
    with ``INSERT ... ON CONFLICT DO NOTHING`` so concurrent first receipts converge on one row),
  * appends an immutable ``StockTransaction`` and an audit log entry.

Database CHECK constraints are the last line of defence for non-negative balances.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Case, Count, DecimalField, ExpressionWrapper, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce, Greatest
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import record

from .models import (
    QTY,
    InventoryItem,
    StockReservation,
    StockStatus,
    StockTransaction,
    Warehouse,
    WarehouseLocation,
)

TT = StockTransaction.TransactionType
ST = StockTransaction.SourceType
ZERO = Decimal("0")
_QUANT = Decimal(1).scaleb(-QTY["decimal_places"])
_MAX = Decimal(10) ** (QTY["max_digits"] - QTY["decimal_places"])

INBOUND = {TT.RECEIPT, TT.ADJUSTMENT_IN, TT.TRANSFER_IN}
OUTBOUND = {TT.ISSUE, TT.ADJUSTMENT_OUT, TT.TRANSFER_OUT}


class InventoryError(ValidationError):
    """Business-rule violation; rendered as HTTP 400 by the API exception handler."""


# --------------------------------------------------------------------------- validation helpers
def positive_quantity(value, field: str = "quantity") -> Decimal:
    """Parse ``value`` as a strictly positive, finite Decimal with at most 4 decimal places."""
    if isinstance(value, bool) or value is None or value == "":
        raise InventoryError({field: "A quantity is required."})
    try:
        qty = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except (InvalidOperation, ValueError, TypeError):
        raise InventoryError({field: "Quantity must be a number."}) from None
    if not qty.is_finite():
        raise InventoryError({field: "Quantity must be a finite number."})
    if qty <= 0:
        raise InventoryError({field: "Quantity must be greater than zero."})
    if qty != qty.quantize(_QUANT):
        raise InventoryError({field: f"Quantity allows at most {QTY['decimal_places']} decimal places."})
    if qty >= _MAX:
        raise InventoryError({field: "Quantity is too large."})
    return qty.quantize(_QUANT)


def _check_location(warehouse: Warehouse, location: WarehouseLocation | None, field: str = "location") -> None:
    if location is not None and location.warehouse_id != warehouse.pk:
        raise InventoryError({field: f"Location {location.code} does not belong to warehouse {warehouse.code}."})


def _check_active(warehouse: Warehouse, location: WarehouseLocation | None, prefix: str = "") -> None:
    if warehouse.deleted_at is not None or not warehouse.is_active:
        raise InventoryError({f"{prefix}warehouse": f"Warehouse {warehouse.code} is inactive."})
    if location is not None and (location.deleted_at is not None or not location.is_active):
        raise InventoryError({f"{prefix}location": f"Location {location.code} is inactive."})


def _identity(component, warehouse, location, lot_batch: str) -> dict:
    return {"component": component, "warehouse": warehouse, "location": location, "lot_batch": lot_batch or ""}


def _ensure_row(component, warehouse, location, lot_batch: str) -> None:
    """Create the balance row if missing without racing (INSERT ... ON CONFLICT DO NOTHING).

    A concurrent inserter of the same identity blocks on the unique index until the other
    transaction commits, then does nothing, so exactly one row ever exists.
    """
    InventoryItem.objects.bulk_create([InventoryItem(**_identity(component, warehouse, location, lot_batch))], ignore_conflicts=True)


def _lock(component, warehouse, location, lot_batch: str) -> InventoryItem | None:
    return (
        InventoryItem.objects.select_for_update()
        .filter(**_identity(component, warehouse, location, lot_batch))
        .order_by("pk")
        .first()
    )


def _lock_many(identities: list[dict]) -> list[InventoryItem]:
    """Lock several balance rows in primary-key order (prevents deadlocks between opposite transfers)."""
    q = Q()
    for ident in identities:
        q |= Q(**ident)
    rows = list(InventoryItem.objects.select_for_update().filter(q).order_by("pk"))
    return rows


def _append(item: InventoryItem, ttype: str, signed_qty: Decimal, user, **extra) -> StockTransaction:
    return StockTransaction.objects.create(
        transaction_type=ttype,
        component_id=item.component_id,
        warehouse_id=item.warehouse_id,
        location_id=item.location_id,
        lot_batch=item.lot_batch,
        quantity=signed_qty,
        quantity_on_hand_after=item.quantity_on_hand,
        quantity_reserved_after=item.quantity_reserved,
        performed_by=user if (user is not None and user.is_authenticated) else None,
        **extra,
    )


def _audit(item: InventoryItem, txn: StockTransaction, user, request=None) -> None:
    record(
        AuditAction.STOCK_TRANSACTION,
        entity_type="inventory.inventoryitem",
        entity_id=item.pk,
        entity_repr=str(item),
        new_value={
            "transaction_id": txn.pk,
            "transaction_type": txn.transaction_type,
            "quantity": str(txn.quantity),
            "quantity_on_hand": str(item.quantity_on_hand),
            "quantity_reserved": str(item.quantity_reserved),
        },
        metadata={"reason": txn.reason, "source_type": txn.source_type, "source_id": txn.source_id, "reference": txn.reference},
        user=user,
        request=request,
    )


def _apply(item: InventoryItem, ttype: str, qty: Decimal) -> Decimal:
    """Apply a movement to a LOCKED row, enforcing availability. Returns the signed ledger quantity."""
    if ttype in INBOUND:
        item.quantity_on_hand += qty
        return qty
    if ttype in OUTBOUND:
        if item.quantity_available < qty:
            raise InventoryError(
                {"quantity": f"Insufficient available stock: available {item.quantity_available}, requested {qty}."}
            )
        item.quantity_on_hand -= qty
        return -qty
    if ttype == TT.RESERVATION:
        if item.quantity_available < qty:
            raise InventoryError(
                {"quantity": f"Insufficient available stock to reserve: available {item.quantity_available}, requested {qty}."}
            )
        item.quantity_reserved += qty
        return qty
    if ttype == TT.RELEASE_RESERVATION:
        if item.quantity_reserved < qty:
            raise InventoryError({"quantity": "Cannot release more than is currently reserved."})
        item.quantity_reserved -= qty
        return -qty
    raise InventoryError({"transaction_type": "Unsupported transaction type."})


# --------------------------------------------------------------------------- operations
@dataclass
class Movement:
    component: object
    warehouse: Warehouse
    location: WarehouseLocation | None
    quantity: object
    lot_batch: str = ""
    reason: str = ""
    notes: str = ""
    reference: str = ""
    unit_cost: Decimal | None = None
    currency: str = ""
    source_type: str = ST.MANUAL
    source_id: str = ""


def _single_movement(ttype: str, m: Movement, user, request=None) -> tuple[StockTransaction, InventoryItem]:
    qty = positive_quantity(m.quantity)
    _check_location(m.warehouse, m.location)
    if ttype in INBOUND:
        _check_active(m.warehouse, m.location)
    if m.unit_cost is not None and m.unit_cost < 0:
        raise InventoryError({"unit_cost": "Unit cost cannot be negative."})

    if ttype in INBOUND:
        _ensure_row(m.component, m.warehouse, m.location, m.lot_batch)
    item = _lock(m.component, m.warehouse, m.location, m.lot_batch)
    if item is None:
        raise InventoryError({"quantity": "There is no stock of this component at the selected warehouse/location/lot."})

    signed = _apply(item, ttype, qty)
    item.save(update_fields=["quantity_on_hand", "quantity_reserved", "updated_at"])
    txn = _append(
        item, ttype, signed, user,
        reason=m.reason, notes=m.notes, reference=m.reference,
        unit_cost=m.unit_cost, currency=(m.currency or "").upper(),
        source_type=m.source_type, source_id=str(m.source_id or ""),
    )
    _audit(item, txn, user, request)
    return txn, item


@transaction.atomic
def receive_stock(m: Movement, user, request=None):
    return _single_movement(TT.RECEIPT, m, user, request)


@transaction.atomic
def issue_stock(m: Movement, user, request=None):
    return _single_movement(TT.ISSUE, m, user, request)


@transaction.atomic
def adjust_stock(m: Movement, direction: str, user, request=None):
    if direction not in ("IN", "OUT"):
        raise InventoryError({"direction": "Direction must be IN or OUT."})
    if not (m.reason or "").strip():
        raise InventoryError({"reason": "A reason is required for stock adjustments."})
    return _single_movement(TT.ADJUSTMENT_IN if direction == "IN" else TT.ADJUSTMENT_OUT, m, user, request)


@transaction.atomic
def transfer_stock(
    component, from_warehouse, from_location, to_warehouse, to_location, quantity, user,
    *, lot_batch: str = "", reason: str = "", notes: str = "", reference: str = "", request=None,
):
    qty = positive_quantity(quantity)
    _check_location(from_warehouse, from_location, "from_location")
    _check_location(to_warehouse, to_location, "to_location")
    _check_active(to_warehouse, to_location, prefix="to_")
    if from_warehouse.pk == to_warehouse.pk and (from_location.pk if from_location else None) == (
        to_location.pk if to_location else None
    ):
        raise InventoryError({"to_location": "Source and destination must differ."})

    src_ident = _identity(component, from_warehouse, from_location, lot_batch)
    dst_ident = _identity(component, to_warehouse, to_location, lot_batch)
    _ensure_row(component, to_warehouse, to_location, lot_batch)
    rows = _lock_many([src_ident, dst_ident])

    def pick(ident):
        loc_id = ident["location"].pk if ident["location"] else None
        for r in rows:
            if r.warehouse_id == ident["warehouse"].pk and r.location_id == loc_id:
                return r
        return None

    src, dst = pick(src_ident), pick(dst_ident)
    if src is None:
        raise InventoryError({"quantity": "There is no stock of this component at the source location."})

    group = uuid.uuid4()
    common = {"reason": reason, "notes": notes, "reference": reference, "source_type": ST.TRANSFER,
              "source_id": str(group), "transfer_group_id": group}
    out_signed = _apply(src, TT.TRANSFER_OUT, qty)
    src.save(update_fields=["quantity_on_hand", "quantity_reserved", "updated_at"])
    out_txn = _append(src, TT.TRANSFER_OUT, out_signed, user, **common)
    in_signed = _apply(dst, TT.TRANSFER_IN, qty)
    dst.save(update_fields=["quantity_on_hand", "quantity_reserved", "updated_at"])
    in_txn = _append(dst, TT.TRANSFER_IN, in_signed, user, **common)
    _audit(src, out_txn, user, request)
    _audit(dst, in_txn, user, request)
    return out_txn, in_txn


@transaction.atomic
def reserve_stock(
    component, warehouse, location, quantity, user,
    *, lot_batch: str = "", project=None, bom_revision=None, reference_type: str = "", reference_id: str = "",
    notes: str = "", request=None,
) -> StockReservation:
    qty = positive_quantity(quantity)
    _check_location(warehouse, location)
    item = _lock(component, warehouse, location, lot_batch)
    if item is None:
        raise InventoryError({"quantity": "There is no stock of this component at the selected warehouse/location/lot."})
    signed = _apply(item, TT.RESERVATION, qty)
    item.save(update_fields=["quantity_reserved", "updated_at"])
    reservation = StockReservation.objects.create(
        inventory_item=item, component=component, warehouse=warehouse, location=location, lot_batch=item.lot_batch,
        quantity=qty, project=project, bom_revision=bom_revision,
        reference_type=reference_type, reference_id=str(reference_id or ""), notes=notes,
        created_by=user if user and user.is_authenticated else None,
    )
    txn = _append(item, TT.RESERVATION, signed, user, source_type=ST.RESERVATION, source_id=str(reservation.pk),
                  reason="Reservation created", notes=notes)
    _audit(item, txn, user, request)
    return reservation


def _close_reservation(reservation_id, user, new_status: str, request=None) -> StockReservation:
    try:
        reservation = StockReservation.objects.select_for_update().get(pk=reservation_id)
    except StockReservation.DoesNotExist:
        raise InventoryError({"reservation": "Reservation not found."}) from None
    if reservation.status != StockReservation.Status.ACTIVE:
        raise InventoryError({"reservation": f"Reservation is already {reservation.status.lower()}."})
    if reservation.inventory_item_id is None:
        raise InventoryError({"reservation": "Legacy reservation is not linked to a stock row; resolve manually."})
    item = InventoryItem.objects.select_for_update().get(pk=reservation.inventory_item_id)
    signed = _apply(item, TT.RELEASE_RESERVATION, reservation.quantity)
    item.save(update_fields=["quantity_reserved", "updated_at"])
    reservation.status = new_status
    reservation.released_at = timezone.now()
    reservation.released_by = user if user and user.is_authenticated else None
    reservation.save(update_fields=["status", "released_at", "released_by", "updated_at"])
    reason = "Reservation released" if new_status == StockReservation.Status.RELEASED else "Reservation cancelled"
    txn = _append(item, TT.RELEASE_RESERVATION, signed, user, source_type=ST.RESERVATION,
                  source_id=str(reservation.pk), reason=reason)
    _audit(item, txn, user, request)
    return reservation


@transaction.atomic
def release_reservation(reservation_id, user, request=None) -> StockReservation:
    return _close_reservation(reservation_id, user, StockReservation.Status.RELEASED, request)


@transaction.atomic
def cancel_reservation(reservation_id, user, request=None) -> StockReservation:
    return _close_reservation(reservation_id, user, StockReservation.Status.CANCELLED, request)


@transaction.atomic
def set_stock_levels(item: InventoryItem, user, *, minimum_stock=None, reorder_level=None, maximum_stock=None, request=None):
    """Configure thresholds. Never touches balances."""
    from apps.audit.services import record_update, snapshot

    old = snapshot(item)
    for name, value in (("minimum_stock", minimum_stock), ("reorder_level", reorder_level)):
        if value is not None:
            if value < 0:
                raise InventoryError({name: "Must be zero or greater."})
            setattr(item, name, value)
    if maximum_stock is not None:
        if maximum_stock < 0:
            raise InventoryError({"maximum_stock": "Must be zero or greater."})
        item.maximum_stock = maximum_stock
    if item.maximum_stock is not None and item.maximum_stock and item.maximum_stock < max(item.minimum_stock, item.reorder_level):
        raise InventoryError({"maximum_stock": "Maximum stock must be at least the minimum/reorder level."})
    item.save(update_fields=["minimum_stock", "reorder_level", "maximum_stock", "updated_at"])
    record_update(item, old, user=user, request=request)
    return item


# --------------------------------------------------------------------------- queries
_DEC = DecimalField(max_digits=QTY["max_digits"], decimal_places=QTY["decimal_places"])


def annotate_stock_status(qs):
    """SQL version of ``models.compute_stock_status`` (keep both in sync)."""
    available = ExpressionWrapper(F("quantity_on_hand") - F("quantity_reserved"), output_field=_DEC)
    threshold = Greatest(F("minimum_stock"), F("reorder_level"))
    return qs.annotate(available_qty=available, threshold_qty=threshold).annotate(
        stock_status=Case(
            When(available_qty__lte=0, then=Value(StockStatus.OUT_OF_STOCK)),
            When(Q(threshold_qty__gt=0) & Q(available_qty__lte=F("threshold_qty")), then=Value(StockStatus.LOW_STOCK)),
            default=Value(StockStatus.IN_STOCK),
        )
    )


def stock_summary(qs=None) -> dict:
    """Dataset-wide totals computed in the database (never in the browser)."""
    qs = annotate_stock_status(qs if qs is not None else InventoryItem.objects.all())
    agg = qs.aggregate(
        stock_rows=Count("id"),
        components=Count("component", distinct=True),
        warehouses=Count("warehouse", distinct=True),
        total_on_hand=Coalesce(Sum("quantity_on_hand"), ZERO, output_field=_DEC),
        total_reserved=Coalesce(Sum("quantity_reserved"), ZERO, output_field=_DEC),
        out_of_stock=Count("id", filter=Q(stock_status=StockStatus.OUT_OF_STOCK)),
        low_stock=Count("id", filter=Q(stock_status=StockStatus.LOW_STOCK)),
        in_stock=Count("id", filter=Q(stock_status=StockStatus.IN_STOCK)),
    )
    agg["total_available"] = agg["total_on_hand"] - agg["total_reserved"]
    agg["active_reservations"] = StockReservation.objects.filter(status=StockReservation.Status.ACTIVE).count()
    return agg


def bom_inventory_availability(bom_revision, build_quantity=1) -> dict:
    """Availability of a BOM revision against current stock.

    Identical components on several BOM lines are aggregated before comparison:
        required  = sum(line.quantity) * build_quantity
        available = on_hand - reserved       (all active warehouses)
        shortage  = max(required - available, 0)
    Two queries regardless of BOM size (no N+1).
    """
    from apps.bom.models import BOMItem

    build = positive_quantity(build_quantity, "build_quantity")
    lines = (
        BOMItem.objects.filter(revision=bom_revision)
        .values("component_id", "component__internal_part_number", "component__mpn", "component__name")
        .annotate(per_board=Sum("quantity"), line_count=Count("id"))
        .order_by("component__internal_part_number")
    )
    component_ids = [line["component_id"] for line in lines]
    stock = {
        row["component_id"]: row
        for row in InventoryItem.objects.filter(
            component_id__in=component_ids, warehouse__deleted_at__isnull=True, warehouse__is_active=True
        )
        .values("component_id")
        .annotate(
            on_hand=Coalesce(Sum("quantity_on_hand"), ZERO, output_field=_DEC),
            reserved=Coalesce(Sum("quantity_reserved"), ZERO, output_field=_DEC),
        )
    }
    rows, short_count = [], 0
    for line in lines:
        s = stock.get(line["component_id"], {})
        on_hand, reserved = s.get("on_hand", ZERO), s.get("reserved", ZERO)
        available = on_hand - reserved
        required = line["per_board"] * build
        shortage = max(required - available, ZERO)
        short_count += shortage > 0
        rows.append({
            "component_id": line["component_id"],
            "internal_part_number": line["component__internal_part_number"],
            "mpn": line["component__mpn"],
            "name": line["component__name"],
            "bom_lines": line["line_count"],
            "quantity_per_board": line["per_board"],
            "required": required,
            "on_hand": on_hand,
            "reserved": reserved,
            "available": available,
            "shortage": shortage,
            "status": "SHORTAGE" if shortage > 0 else "SUFFICIENT",
        })
    return {
        "bom_revision": bom_revision.pk,
        "revision_status": bom_revision.status,
        "build_quantity": build,
        "components": len(rows),
        "components_short": short_count,
        "items": rows,
    }

"""Supplier & SupplierPart business logic."""
from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
from typing import Iterable

from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.components.services import normalize_identifier, rebuild_search_document
from apps.core.exceptions import Conflict

from .models import (
    Supplier,
    SupplierContact,
    SupplierPart,
    SupplierPriceBreak,
    SupplierPriceHistory,
)


def generate_supplier_code() -> str:
    """Generate the next sequential SUP-NNNN code."""
    count = Supplier.all_objects.count() + 1
    while True:
        code = f"SUP-{count:04d}"
        if not Supplier.all_objects.filter(code__iexact=code).exists():
            return code
        count += 1


def effective_order_quantity(requested: Decimal, moq: Decimal, order_multiple: Decimal) -> Decimal:
    """Compute the minimum purchasable quantity >= requested respecting MOQ and order multiple."""
    qty = max(Decimal(str(requested)), Decimal(str(moq or 1)))
    mult = Decimal(str(order_multiple or 1))
    if mult > 0:
        steps = (qty / mult).to_integral_value(rounding=ROUND_CEILING)
        qty = steps * mult
    return qty.quantize(Decimal("0.0001"))


@transaction.atomic
def set_price_breaks(
    supplier_part: SupplierPart,
    breaks_data: Iterable[dict],
    *,
    user=None,
    reference: str = "",
) -> list[SupplierPriceBreak]:
    """Replace price breaks on a SupplierPart and append immutable history entries for new/changed breaks."""
    existing = {b.min_quantity: b for b in supplier_part.price_breaks.all()}
    seen_qtys: set[Decimal] = set()
    kept_ids: list[int] = []
    result: list[SupplierPriceBreak] = []

    for row in breaks_data:
        min_qty = Decimal(str(row["min_quantity"])).quantize(Decimal("0.0001"))
        unit_price = Decimal(str(row["unit_price"])).quantize(Decimal("0.000001"))
        currency = (row.get("currency") or supplier_part.currency or "USD").strip().upper()
        if min_qty <= 0:
            raise ValidationError({"price_breaks": "Minimum quantity must be greater than zero."})
        if unit_price < 0:
            raise ValidationError({"price_breaks": "Unit price cannot be negative."})
        if min_qty in seen_qtys:
            raise ValidationError({"price_breaks": f"Duplicate price break for quantity {min_qty}."})
        seen_qtys.add(min_qty)

        prev = existing.get(min_qty)
        if prev is not None:
            changed = prev.unit_price != unit_price or prev.currency != currency
            prev.unit_price = unit_price
            prev.currency = currency
            prev.save(update_fields=["unit_price", "currency", "updated_at"])
            obj = prev
        else:
            changed = True
            obj = SupplierPriceBreak.objects.create(
                supplier_part=supplier_part,
                min_quantity=min_qty,
                unit_price=unit_price,
                currency=currency,
            )
        kept_ids.append(obj.pk)
        result.append(obj)
        if changed:
            SupplierPriceHistory.objects.create(
                supplier_part=supplier_part,
                min_quantity=min_qty,
                unit_price=unit_price,
                currency=currency,
                source=SupplierPriceHistory.Source.PRICE_BREAK,
                reference=reference,
                recorded_by=user if (user and getattr(user, "is_authenticated", False)) else None,
            )

    supplier_part.price_breaks.exclude(pk__in=kept_ids).delete()
    return sorted(result, key=lambda b: b.min_quantity)


@transaction.atomic
def create_supplier_part(
    *,
    data: dict,
    price_breaks: list[dict] | None = None,
    user=None,
    request=None,
) -> SupplierPart:
    spn = " ".join(str(data.get("supplier_part_number", "")).split())
    norm = normalize_identifier(spn)
    if not norm:
        raise ValidationError({"supplier_part_number": ["Supplier part number is required."]})
    supplier = data["supplier"]
    if SupplierPart.objects.filter(supplier=supplier, supplier_part_number_normalized=norm).exists():
        raise ValidationError(
            {"supplier_part_number": [f"Supplier {supplier.code} already has part number '{spn}'."]}
        )

    part = SupplierPart(
        **{
            **data,
            "supplier_part_number": spn,
            "supplier_part_number_normalized": norm,
            "currency": (data.get("currency") or supplier.currency or "USD").strip().upper(),
        }
    )
    if user and getattr(user, "is_authenticated", False):
        part.created_by = part.updated_by = user
    part.save()

    SupplierPriceHistory.objects.create(
        supplier_part=part,
        min_quantity=part.moq,
        unit_price=part.unit_price,
        currency=part.currency,
        source=SupplierPriceHistory.Source.MANUAL,
        reference="Initial price",
        recorded_by=user if (user and getattr(user, "is_authenticated", False)) else None,
    )
    if price_breaks is not None:
        set_price_breaks(part, price_breaks, user=user, reference="Initial price breaks")

    rebuild_search_document(part.component)
    audit.record_create(part, request=request, user=user)
    return part


@transaction.atomic
def update_supplier_part(
    part: SupplierPart,
    *,
    data: dict,
    price_breaks: list[dict] | None = None,
    user=None,
    request=None,
) -> SupplierPart:
    part = SupplierPart.objects.select_for_update().get(pk=part.pk)
    old = audit.snapshot(part)
    old_price = part.unit_price
    old_currency = part.currency

    if "supplier_part_number" in data:
        spn = " ".join(str(data["supplier_part_number"]).split())
        norm = normalize_identifier(spn)
        if not norm:
            raise ValidationError({"supplier_part_number": ["Supplier part number is required."]})
        supplier = data.get("supplier", part.supplier)
        if (
            SupplierPart.objects.filter(supplier=supplier, supplier_part_number_normalized=norm)
            .exclude(pk=part.pk)
            .exists()
        ):
            raise ValidationError(
                {"supplier_part_number": [f"Supplier {supplier.code} already has part number '{spn}'."]}
            )
        data["supplier_part_number"] = spn
        data["supplier_part_number_normalized"] = norm

    if "currency" in data and data["currency"]:
        data["currency"] = data["currency"].strip().upper()

    for key, value in data.items():
        setattr(part, key, value)
    if user and getattr(user, "is_authenticated", False):
        part.updated_by = user
    part.save()

    if part.unit_price != old_price or part.currency != old_currency:
        SupplierPriceHistory.objects.create(
            supplier_part=part,
            min_quantity=part.moq,
            unit_price=part.unit_price,
            currency=part.currency,
            source=SupplierPriceHistory.Source.MANUAL,
            reference="Price update",
            recorded_by=user if (user and getattr(user, "is_authenticated", False)) else None,
        )

    if price_breaks is not None:
        set_price_breaks(part, price_breaks, user=user, reference="Updated price breaks")

    rebuild_search_document(part.component)
    audit.record_update(part, old, request=request, user=user)
    return part


@transaction.atomic
def delete_supplier_part(part: SupplierPart, *, user=None, request=None) -> None:
    from apps.purchasing.models import PurchaseOrder, PurchaseOrderItem

    open_statuses = [
        PurchaseOrder.Status.DRAFT,
        PurchaseOrder.Status.APPROVED,
        PurchaseOrder.Status.SENT,
        PurchaseOrder.Status.PARTIALLY_RECEIVED,
    ]
    if PurchaseOrderItem.objects.filter(
        supplier_part=part,
        purchase_order__status__in=open_statuses,
    ).exists():
        raise Conflict("Supplier part is referenced by an open purchase order and cannot be deleted.")
    component = part.component
    part.soft_delete(user)
    rebuild_search_document(component)
    audit.record_delete(part, request=request, user=user, soft=True)


def check_supplier_deletable(supplier: Supplier) -> None:
    from apps.purchasing.models import PurchaseOrder

    open_statuses = [
        PurchaseOrder.Status.DRAFT,
        PurchaseOrder.Status.APPROVED,
        PurchaseOrder.Status.SENT,
        PurchaseOrder.Status.PARTIALLY_RECEIVED,
    ]
    if PurchaseOrder.objects.filter(supplier=supplier, status__in=open_statuses).exists():
        raise Conflict("Supplier has open purchase orders. Complete or cancel them before deleting the supplier.")


def compare_supplier_parts(component, quantity: Decimal = Decimal("1")) -> dict:
    """Compare all active supplier offerings for ``component`` at ``quantity``."""
    try:
        req_qty = Decimal(str(quantity))
    except Exception:
        raise ValidationError({"quantity": "Quantity must be a positive number."}) from None
    if req_qty <= 0:
        raise ValidationError({"quantity": "Quantity must be greater than zero."})

    parts = (
        SupplierPart.objects.filter(
            component=component,
            is_active=True,
            supplier__deleted_at__isnull=True,
            supplier__is_active=True,
        )
        .exclude(supplier__status=Supplier.Status.INACTIVE)
        .select_related("supplier")
        .prefetch_related("price_breaks")
    )

    offers = []
    for p in parts:
        order_qty = effective_order_quantity(req_qty, p.moq, p.order_multiple)
        unit_price = p.price_for_quantity(order_qty)
        extended = (order_qty * unit_price).quantize(Decimal("0.0001"))
        lead_time = p.lead_time_days if p.lead_time_days is not None else p.supplier.lead_time_days
        offers.append(
            {
                "supplier_part_id": p.id,
                "supplier_id": p.supplier_id,
                "supplier_code": p.supplier.code,
                "supplier_name": p.supplier.name,
                "supplier_status": p.supplier.status,
                "supplier_part_number": p.supplier_part_number,
                "manufacturer_part_number": p.manufacturer_part_number or component.mpn,
                "packaging": p.packaging,
                "currency": p.currency,
                "moq": p.moq,
                "order_multiple": p.order_multiple,
                "lead_time_days": lead_time,
                "is_preferred": p.is_preferred,
                "product_url": p.product_url,
                "requested_quantity": req_qty.quantize(Decimal("0.0001")),
                "effective_order_quantity": order_qty,
                "effective_unit_price": unit_price,
                "extended_price": extended,
            }
        )

    offers.sort(
        key=lambda o: (
            not o["is_preferred"],
            o["effective_unit_price"],
            o["lead_time_days"] if o["lead_time_days"] is not None else 999999,
        )
    )
    return {
        "component_id": component.id,
        "internal_part_number": component.internal_part_number,
        "mpn": component.mpn,
        "requested_quantity": req_qty.quantize(Decimal("0.0001")),
        "offers": offers,
    }

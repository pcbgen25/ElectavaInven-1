"""Purchasing business operations: Purchase Requests, Purchase Orders, and Goods Receipts."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Iterable

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.audit.models import AuditAction
from apps.core.exceptions import Conflict
from apps.inventory.models import StockTransaction
from apps.inventory.services import Movement, bom_inventory_availability, positive_quantity, receive_stock
from apps.suppliers.models import Supplier, SupplierPart, SupplierPriceHistory
from apps.suppliers.services import compare_supplier_parts, effective_order_quantity

from .models import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequest,
    PurchaseRequestItem,
    PurchaseSequence,
)

ZERO = Decimal("0.0000")


def next_document_number(prefix: str, model_cls, field_name: str) -> str:
    """Concurrency-safe document sequence generator (PR-0001, PO-0001, GRN-0001)."""
    try:
        with transaction.atomic():
            PurchaseSequence.objects.get_or_create(prefix=prefix)
    except IntegrityError:
        pass
    with transaction.atomic():
        seq = PurchaseSequence.objects.select_for_update().get(prefix=prefix)
        while True:
            seq.last_value += 1
            candidate = f"{prefix}-{seq.last_value:04d}"
            if not model_cls.objects.filter(**{field_name: candidate}).exists():
                break
        seq.save(update_fields=["last_value"])
    return candidate


# --------------------------------------------------------------------------- Purchase Requests
@transaction.atomic
def create_purchase_request(
    *,
    data: dict,
    items: Iterable[dict],
    user=None,
    request=None,
) -> PurchaseRequest:
    items_list = list(items or [])
    if not items_list:
        raise ValidationError({"items": ["At least one line item is required on a purchase request."]})

    req_number = (data.get("request_number") or "").strip().upper()
    if not req_number:
        req_number = next_document_number("PR", PurchaseRequest, "request_number")
    elif PurchaseRequest.all_objects.filter(request_number__iexact=req_number).exists():
        raise ValidationError({"request_number": ["This request number is already used."]})

    pr = PurchaseRequest(
        **{
            **data,
            "request_number": req_number,
            "status": PurchaseRequest.Status.DRAFT,
        }
    )
    if user and getattr(user, "is_authenticated", False):
        pr.created_by = pr.updated_by = user
    pr.save()

    _replace_pr_items(pr, items_list)
    audit.record_create(pr, request=request, user=user, extra={"item_count": len(items_list)})
    return pr


def _replace_pr_items(pr: PurchaseRequest, items_list: list[dict]) -> None:
    if pr.status not in (PurchaseRequest.Status.DRAFT, PurchaseRequest.Status.SUBMITTED):
        raise ValidationError({"status": f"Cannot modify items when request is {pr.status.lower()}."})
    if not items_list:
        raise ValidationError({"items": ["At least one line item is required."]})

    pr.items.all().delete()
    for row in items_list:
        qty = positive_quantity(row.get("quantity"), "quantity")
        supplier_part = row.get("supplier_part")
        preferred_supplier = row.get("preferred_supplier")
        if supplier_part and not preferred_supplier:
            preferred_supplier = supplier_part.supplier
        est_price = row.get("estimated_unit_price")
        if est_price is None and supplier_part is not None:
            est_price = supplier_part.price_for_quantity(qty)
        currency = (row.get("currency") or (supplier_part.currency if supplier_part else "USD") or "USD").strip().upper()

        PurchaseRequestItem.objects.create(
            purchase_request=pr,
            component=row["component"],
            preferred_supplier=preferred_supplier,
            supplier_part=supplier_part,
            quantity=qty,
            estimated_unit_price=est_price,
            currency=currency,
            notes=row.get("notes", "")[:300],
        )


@transaction.atomic
def update_purchase_request(
    pr: PurchaseRequest,
    *,
    data: dict,
    items: list[dict] | None = None,
    user=None,
    request=None,
) -> PurchaseRequest:
    pr = PurchaseRequest.objects.select_for_update().get(pk=pr.pk)
    if pr.status not in (PurchaseRequest.Status.DRAFT, PurchaseRequest.Status.SUBMITTED):
        raise ValidationError({"status": f"Purchase request in status {pr.status} cannot be edited."})
    old = audit.snapshot(pr)
    data.pop("request_number", None)
    data.pop("status", None)
    for key, value in data.items():
        setattr(pr, key, value)
    if user and getattr(user, "is_authenticated", False):
        pr.updated_by = user
    pr.save()
    if items is not None:
        _replace_pr_items(pr, items)
    audit.record_update(pr, old, request=request, user=user)
    return pr


@transaction.atomic
def submit_purchase_request(pr: PurchaseRequest, *, user=None, request=None) -> PurchaseRequest:
    pr = PurchaseRequest.objects.select_for_update().get(pk=pr.pk)
    if pr.status != PurchaseRequest.Status.DRAFT:
        raise ValidationError({"status": f"Only DRAFT requests can be submitted (current: {pr.status})."})
    if not pr.items.exists():
        raise ValidationError({"items": "Cannot submit an empty purchase request."})
    old = audit.snapshot(pr)
    pr.status = PurchaseRequest.Status.SUBMITTED
    pr.submitted_by = user if (user and getattr(user, "is_authenticated", False)) else None
    pr.submitted_at = timezone.now()
    if user and getattr(user, "is_authenticated", False):
        pr.updated_by = user
    pr.save(update_fields=["status", "submitted_by", "submitted_at", "updated_by", "updated_at"])
    audit.record_update(pr, old, request=request, user=user)
    return pr


@transaction.atomic
def approve_purchase_request(pr: PurchaseRequest, *, user=None, notes: str = "", request=None) -> PurchaseRequest:
    pr = PurchaseRequest.objects.select_for_update().get(pk=pr.pk)
    if pr.status not in (PurchaseRequest.Status.DRAFT, PurchaseRequest.Status.SUBMITTED):
        raise ValidationError({"status": f"Purchase request in status {pr.status} cannot be approved."})
    if not pr.items.exists():
        raise ValidationError({"items": "Cannot approve an empty purchase request."})
    old_status = pr.status
    pr.status = PurchaseRequest.Status.APPROVED
    pr.reviewed_by = user if (user and getattr(user, "is_authenticated", False)) else None
    pr.reviewed_at = timezone.now()
    pr.review_notes = notes or ""
    if user and getattr(user, "is_authenticated", False):
        pr.updated_by = user
    pr.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes", "updated_by", "updated_at"])
    audit.record(
        AuditAction.PURCHASE_APPROVAL,
        entity_type="purchasing.purchaserequest",
        entity_id=pr.pk,
        entity_repr=str(pr),
        old_value={"status": old_status},
        new_value={"status": pr.status, "review_notes": pr.review_notes},
        user=user,
        request=request,
    )
    return pr


@transaction.atomic
def reject_purchase_request(pr: PurchaseRequest, *, user=None, notes: str = "", request=None) -> PurchaseRequest:
    pr = PurchaseRequest.objects.select_for_update().get(pk=pr.pk)
    if pr.status not in (PurchaseRequest.Status.DRAFT, PurchaseRequest.Status.SUBMITTED):
        raise ValidationError({"status": f"Purchase request in status {pr.status} cannot be rejected."})
    old_status = pr.status
    pr.status = PurchaseRequest.Status.REJECTED
    pr.reviewed_by = user if (user and getattr(user, "is_authenticated", False)) else None
    pr.reviewed_at = timezone.now()
    pr.review_notes = notes or ""
    if user and getattr(user, "is_authenticated", False):
        pr.updated_by = user
    pr.save(update_fields=["status", "reviewed_by", "reviewed_at", "review_notes", "updated_by", "updated_at"])
    audit.record(
        AuditAction.PURCHASE_APPROVAL,
        entity_type="purchasing.purchaserequest",
        entity_id=pr.pk,
        entity_repr=str(pr),
        old_value={"status": old_status},
        new_value={"status": pr.status, "review_notes": pr.review_notes},
        user=user,
        request=request,
    )
    return pr


@transaction.atomic
def cancel_purchase_request(pr: PurchaseRequest, *, user=None, notes: str = "", request=None) -> PurchaseRequest:
    pr = PurchaseRequest.objects.select_for_update().get(pk=pr.pk)
    if pr.status == PurchaseRequest.Status.CANCELLED:
        raise ValidationError({"status": "Purchase request is already cancelled."})
    if pr.purchase_orders.exclude(status=PurchaseOrder.Status.CANCELLED).exists():
        raise Conflict("Purchase request has active purchase orders and cannot be cancelled.")
    old = audit.snapshot(pr)
    pr.status = PurchaseRequest.Status.CANCELLED
    if notes:
        pr.review_notes = notes
    if user and getattr(user, "is_authenticated", False):
        pr.updated_by = user
    pr.save(update_fields=["status", "review_notes", "updated_by", "updated_at"])
    audit.record_update(pr, old, request=request, user=user)
    return pr


@transaction.atomic
def create_purchase_request_from_bom_shortage(
    bom_revision,
    build_quantity=Decimal("1"),
    *,
    title: str = "",
    priority: str = PurchaseRequest.Priority.NORMAL,
    needed_by=None,
    notes: str = "",
    apply_moq: bool = False,
    user=None,
    request=None,
) -> PurchaseRequest:
    """Create a PurchaseRequest for all shortage components on ``bom_revision`` at ``build_quantity``."""
    from apps.components.models import Component

    availability = bom_inventory_availability(bom_revision, build_quantity)
    short_rows = [r for r in availability["items"] if r["shortage"] > 0]
    if not short_rows:
        raise ValidationError(
            {"bom_revision": "All BOM components have sufficient available stock for the requested build quantity."}
        )

    comp_map = {
        c.id: c for c in Component.objects.filter(id__in=[r["component_id"] for r in short_rows])
    }

    pr_items = []
    for row in short_rows:
        comp = comp_map[row["component_id"]]
        shortage_qty = Decimal(str(row["shortage"]))
        comparison = compare_supplier_parts(comp, shortage_qty)
        best_offer = comparison["offers"][0] if comparison["offers"] else None

        supplier_part = None
        preferred_supplier = None
        est_price = None
        currency = "USD"
        qty = shortage_qty

        if best_offer is not None:
            supplier_part = SupplierPart.objects.filter(pk=best_offer["supplier_part_id"]).select_related("supplier").first()
            preferred_supplier = supplier_part.supplier if supplier_part else None
            if apply_moq:
                qty = Decimal(str(best_offer["effective_order_quantity"]))
            est_price = Decimal(str(best_offer["effective_unit_price"]))
            currency = best_offer["currency"]

        pr_items.append(
            {
                "component": comp,
                "preferred_supplier": preferred_supplier,
                "supplier_part": supplier_part,
                "quantity": qty,
                "estimated_unit_price": est_price,
                "currency": currency,
                "notes": f"BOM {bom_revision.bom.name} {bom_revision.revision_number} shortage ({shortage_qty} short for {availability['build_quantity']} builds)",
            }
        )

    default_title = (
        title.strip()
        if title and title.strip()
        else f"BOM Shortage: {bom_revision.bom.name} ({bom_revision.revision_number}) x {availability['build_quantity']}"
    )
    return create_purchase_request(
        data={
            "title": default_title,
            "project": bom_revision.bom.project,
            "bom_revision": bom_revision,
            "build_quantity": availability["build_quantity"],
            "priority": priority or PurchaseRequest.Priority.NORMAL,
            "needed_by": needed_by,
            "notes": notes or f"Auto-generated from BOM shortage analysis for {bom_revision}.",
        },
        items=pr_items,
        user=user,
        request=request,
    )


# --------------------------------------------------------------------------- Purchase Orders
def _validate_supplier_can_order(supplier: Supplier) -> None:
    if supplier.deleted_at is not None or not supplier.is_active or supplier.status == Supplier.Status.INACTIVE:
        raise ValidationError({"supplier": f"Supplier {supplier.name} is inactive and cannot receive purchase orders."})
    if supplier.status == Supplier.Status.ON_HOLD:
        raise ValidationError({"supplier": f"Supplier {supplier.name} is ON HOLD and cannot receive new purchase orders."})


def recalculate_po_totals(po: PurchaseOrder) -> PurchaseOrder:
    subtotal = sum((item.line_total for item in po.items.all()), ZERO).quantize(Decimal("0.0001"))
    tax = Decimal(str(po.tax_amount or 0)).quantize(Decimal("0.0001"))
    shipping = Decimal(str(po.shipping_amount or 0)).quantize(Decimal("0.0001"))
    discount = Decimal(str(po.discount_amount or 0)).quantize(Decimal("0.0001"))
    total = (subtotal + tax + shipping - discount).quantize(Decimal("0.0001"))
    if total < 0:
        raise ValidationError({"discount_amount": "Discount cannot exceed subtotal plus tax and shipping."})
    po.subtotal = subtotal
    po.tax_amount = tax
    po.shipping_amount = shipping
    po.discount_amount = discount
    po.total_amount = total
    po.save(update_fields=["subtotal", "tax_amount", "shipping_amount", "discount_amount", "total_amount", "updated_at"])
    return po


def _create_po_items(po: PurchaseOrder, items_list: list[dict], *, user=None) -> None:
    if not items_list:
        raise ValidationError({"items": ["At least one line item is required on a purchase order."]})

    for row in items_list:
        comp = row["component"]
        qty = positive_quantity(row.get("quantity_ordered"), "quantity_ordered")
        sp: SupplierPart | None = row.get("supplier_part")
        if sp is not None and sp.supplier_id != po.supplier_id:
            raise ValidationError(
                {"items": f"Supplier part {sp.supplier_part_number} does not belong to supplier {po.supplier.name}."}
            )
        if sp is None:
            sp = (
                SupplierPart.objects.filter(supplier=po.supplier, component=comp, is_active=True)
                .order_by("-is_preferred", "id")
                .first()
            )

        raw_price = row.get("unit_price")
        if raw_price is None:
            unit_price = sp.price_for_quantity(qty) if sp is not None else Decimal("0.000000")
        else:
            unit_price = Decimal(str(raw_price)).quantize(Decimal("0.000001"))
        if unit_price < 0:
            raise ValidationError({"unit_price": "Unit price cannot be negative."})

        line_total = (qty * unit_price).quantize(Decimal("0.0001"))
        item = PurchaseOrderItem.objects.create(
            purchase_order=po,
            component=comp,
            supplier_part=sp,
            purchase_request_item=row.get("purchase_request_item"),
            supplier_part_number_snapshot=(
                row.get("supplier_part_number_snapshot") or (sp.supplier_part_number if sp else "")
            )[:120],
            mpn_snapshot=(row.get("mpn_snapshot") or comp.mpn or "")[:120],
            description_snapshot=(row.get("description_snapshot") or comp.name or "")[:300],
            quantity_ordered=qty,
            quantity_received=ZERO,
            unit_price=unit_price,
            line_total=line_total,
            expected_date=row.get("expected_date") or po.expected_delivery_date,
            notes=(row.get("notes") or "")[:300],
        )

        if sp is not None:
            SupplierPriceHistory.objects.create(
                supplier_part=sp,
                min_quantity=qty,
                unit_price=unit_price,
                currency=po.currency,
                source=SupplierPriceHistory.Source.PURCHASE_ORDER,
                reference=po.po_number,
                recorded_by=user if (user and getattr(user, "is_authenticated", False)) else None,
            )


@transaction.atomic
def create_purchase_order(
    *,
    data: dict,
    items: Iterable[dict],
    user=None,
    request=None,
) -> PurchaseOrder:
    items_list = list(items or [])
    if not items_list:
        raise ValidationError({"items": ["At least one line item is required on a purchase order."]})

    supplier: Supplier = data["supplier"]
    _validate_supplier_can_order(supplier)

    po_number = (data.get("po_number") or "").strip().upper()
    if not po_number:
        po_number = next_document_number("PO", PurchaseOrder, "po_number")
    elif PurchaseOrder.all_objects.filter(po_number__iexact=po_number).exists():
        raise ValidationError({"po_number": ["This PO number is already used."]})

    currency = (data.get("currency") or supplier.currency or "USD").strip().upper()
    exchange_rate = Decimal(str(data.get("exchange_rate") or "1.000000")).quantize(Decimal("0.000001"))
    if exchange_rate <= 0:
        raise ValidationError({"exchange_rate": "Exchange rate must be greater than zero."})

    po = PurchaseOrder(
        **{
            **data,
            "po_number": po_number,
            "status": PurchaseOrder.Status.DRAFT,
            "currency": currency,
            "exchange_rate": exchange_rate,
            "payment_terms_snapshot": data.get("payment_terms_snapshot") or supplier.payment_terms or "",
        }
    )
    if user and getattr(user, "is_authenticated", False):
        po.created_by = po.updated_by = user
    po.save()

    _create_po_items(po, items_list, user=user)
    recalculate_po_totals(po)

    if po.purchase_request_id:
        _sync_purchase_request_ordered_state(po.purchase_request)

    audit.record(
        AuditAction.PURCHASE_ORDER,
        entity_type="purchasing.purchaseorder",
        entity_id=po.pk,
        entity_repr=str(po),
        new_value={
            "po_number": po.po_number,
            "status": po.status,
            "supplier": supplier.code,
            "currency": po.currency,
            "total_amount": str(po.total_amount),
        },
        user=user,
        request=request,
    )
    return po


def _sync_purchase_request_ordered_state(pr: PurchaseRequest) -> None:
    pr = PurchaseRequest.objects.select_for_update().get(pk=pr.pk)
    if pr.status == PurchaseRequest.Status.APPROVED:
        pr.status = PurchaseRequest.Status.ORDERED
        pr.save(update_fields=["status", "updated_at"])


@transaction.atomic
def update_purchase_order(
    po: PurchaseOrder,
    *,
    data: dict,
    items: list[dict] | None = None,
    user=None,
    request=None,
) -> PurchaseOrder:
    po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)
    old = audit.snapshot(po)
    data.pop("po_number", None)
    data.pop("status", None)

    if po.status != PurchaseOrder.Status.DRAFT:
        locked_fields = {"supplier", "currency", "exchange_rate", "tax_amount", "shipping_amount", "discount_amount"}
        attempted = locked_fields.intersection(data.keys())
        if attempted or items is not None:
            raise ValidationError(
                {"status": f"Purchase order {po.po_number} is {po.status.lower()} and its commercial terms/items are locked."}
            )

    if "supplier" in data:
        _validate_supplier_can_order(data["supplier"])
    if "currency" in data and data["currency"]:
        data["currency"] = data["currency"].strip().upper()
    if "exchange_rate" in data and data["exchange_rate"] is not None:
        if Decimal(str(data["exchange_rate"])) <= 0:
            raise ValidationError({"exchange_rate": "Exchange rate must be greater than zero."})

    for key, value in data.items():
        setattr(po, key, value)
    if user and getattr(user, "is_authenticated", False):
        po.updated_by = user
    po.save()

    if items is not None:
        po.items.all().delete()
        _create_po_items(po, items, user=user)
    if po.status == PurchaseOrder.Status.DRAFT:
        recalculate_po_totals(po)

    audit.record_update(po, old, request=request, user=user)
    return po


@transaction.atomic
def create_po_from_purchase_request(
    pr: PurchaseRequest,
    *,
    supplier: Supplier,
    item_ids: list[int] | None = None,
    default_warehouse=None,
    currency: str = "",
    exchange_rate: Decimal = Decimal("1.000000"),
    expected_delivery_date=None,
    notes: str = "",
    apply_moq: bool = False,
    user=None,
    request=None,
) -> PurchaseOrder:
    pr = PurchaseRequest.objects.select_for_update().get(pk=pr.pk)
    if pr.status not in (PurchaseRequest.Status.APPROVED, PurchaseRequest.Status.ORDERED):
        raise ValidationError(
            {"purchase_request": f"Purchase request must be APPROVED before converting to a PO (current: {pr.status})."}
        )
    _validate_supplier_can_order(supplier)

    qs = pr.items.select_related("component", "supplier_part")
    if item_ids:
        qs = qs.filter(id__in=item_ids)
    pr_items = list(qs)
    if not pr_items:
        raise ValidationError({"items": "No matching purchase request items selected."})

    po_items = []
    for pri in pr_items:
        sp = (
            pri.supplier_part
            if (pri.supplier_part_id and pri.supplier_part.supplier_id == supplier.pk)
            else SupplierPart.objects.filter(supplier=supplier, component=pri.component, is_active=True)
            .order_by("-is_preferred", "id")
            .first()
        )
        qty = pri.quantity
        if sp is not None and apply_moq:
            qty = effective_order_quantity(qty, sp.moq, sp.order_multiple)
        unit_price = (
            sp.price_for_quantity(qty)
            if sp is not None
            else (pri.estimated_unit_price if pri.estimated_unit_price is not None else Decimal("0.000000"))
        )
        po_items.append(
            {
                "component": pri.component,
                "supplier_part": sp,
                "purchase_request_item": pri,
                "quantity_ordered": qty,
                "unit_price": unit_price,
                "notes": pri.notes,
            }
        )

    return create_purchase_order(
        data={
            "supplier": supplier,
            "purchase_request": pr,
            "project": pr.project,
            "bom_revision": pr.bom_revision,
            "default_warehouse": default_warehouse,
            "currency": currency or supplier.currency or "USD",
            "exchange_rate": exchange_rate,
            "expected_delivery_date": expected_delivery_date or pr.needed_by,
            "notes": notes or f"Created from {pr.request_number}",
        },
        items=po_items,
        user=user,
        request=request,
    )


@transaction.atomic
def approve_purchase_order(po: PurchaseOrder, *, user=None, request=None) -> PurchaseOrder:
    po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)
    if po.status != PurchaseOrder.Status.DRAFT:
        raise ValidationError({"status": f"Only DRAFT purchase orders can be approved (current: {po.status})."})
    if not po.items.exists():
        raise ValidationError({"items": "Cannot approve an empty purchase order."})
    _validate_supplier_can_order(po.supplier)

    old_status = po.status
    po.status = PurchaseOrder.Status.APPROVED
    po.approved_by = user if (user and getattr(user, "is_authenticated", False)) else None
    po.approved_at = timezone.now()
    if user and getattr(user, "is_authenticated", False):
        po.updated_by = user
    po.save(update_fields=["status", "approved_by", "approved_at", "updated_by", "updated_at"])

    audit.record(
        AuditAction.PURCHASE_APPROVAL,
        entity_type="purchasing.purchaseorder",
        entity_id=po.pk,
        entity_repr=str(po),
        old_value={"status": old_status},
        new_value={"status": po.status, "total_amount": str(po.total_amount), "currency": po.currency},
        user=user,
        request=request,
    )
    return po


@transaction.atomic
def send_purchase_order(po: PurchaseOrder, *, user=None, request=None) -> PurchaseOrder:
    po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)
    if po.status != PurchaseOrder.Status.APPROVED:
        raise ValidationError({"status": f"Only APPROVED purchase orders can be sent (current: {po.status})."})
    old_status = po.status
    po.status = PurchaseOrder.Status.SENT
    po.sent_by = user if (user and getattr(user, "is_authenticated", False)) else None
    po.sent_at = timezone.now()
    if not po.order_date:
        po.order_date = timezone.now().date()
    if user and getattr(user, "is_authenticated", False):
        po.updated_by = user
    po.save(update_fields=["status", "sent_by", "sent_at", "order_date", "updated_by", "updated_at"])

    audit.record(
        AuditAction.PURCHASE_ORDER,
        entity_type="purchasing.purchaseorder",
        entity_id=po.pk,
        entity_repr=str(po),
        old_value={"status": old_status},
        new_value={"status": po.status, "order_date": str(po.order_date)},
        user=user,
        request=request,
    )
    return po


@transaction.atomic
def cancel_purchase_order(po: PurchaseOrder, *, user=None, request=None) -> PurchaseOrder:
    po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)
    if po.status == PurchaseOrder.Status.CANCELLED:
        raise ValidationError({"status": "Purchase order is already cancelled."})
    if po.status in (PurchaseOrder.Status.PARTIALLY_RECEIVED, PurchaseOrder.Status.RECEIVED, PurchaseOrder.Status.CLOSED):
        raise Conflict(f"Cannot cancel purchase order in status {po.status}.")
    if po.items.filter(quantity_received__gt=0).exists() or po.goods_receipts.filter(status=GoodsReceipt.Status.POSTED).exists():
        raise Conflict("Cannot cancel a purchase order that already has received stock.")

    old_status = po.status
    po.status = PurchaseOrder.Status.CANCELLED
    if user and getattr(user, "is_authenticated", False):
        po.updated_by = user
    po.save(update_fields=["status", "updated_by", "updated_at"])

    audit.record(
        AuditAction.PURCHASE_ORDER,
        entity_type="purchasing.purchaseorder",
        entity_id=po.pk,
        entity_repr=str(po),
        old_value={"status": old_status},
        new_value={"status": po.status},
        user=user,
        request=request,
    )
    return po


@transaction.atomic
def close_purchase_order(po: PurchaseOrder, *, user=None, request=None) -> PurchaseOrder:
    po = PurchaseOrder.objects.select_for_update().get(pk=po.pk)
    if po.status not in (PurchaseOrder.Status.RECEIVED, PurchaseOrder.Status.PARTIALLY_RECEIVED):
        raise ValidationError(
            {"status": f"Only RECEIVED or PARTIALLY_RECEIVED purchase orders can be closed (current: {po.status})."}
        )
    old_status = po.status
    po.status = PurchaseOrder.Status.CLOSED
    if user and getattr(user, "is_authenticated", False):
        po.updated_by = user
    po.save(update_fields=["status", "updated_by", "updated_at"])

    audit.record(
        AuditAction.PURCHASE_ORDER,
        entity_type="purchasing.purchaseorder",
        entity_id=po.pk,
        entity_repr=str(po),
        old_value={"status": old_status},
        new_value={"status": po.status},
        user=user,
        request=request,
    )
    return po


# --------------------------------------------------------------------------- Goods Receipts (Atomic with Inventory)
RECEIVABLE_PO_STATUSES = {
    PurchaseOrder.Status.APPROVED,
    PurchaseOrder.Status.SENT,
    PurchaseOrder.Status.PARTIALLY_RECEIVED,
}


@transaction.atomic
def create_goods_receipt(
    *,
    data: dict,
    items: Iterable[dict],
    post_immediately: bool = True,
    user=None,
    request=None,
) -> GoodsReceipt:
    items_list = list(items or [])
    if not items_list:
        raise ValidationError({"items": ["At least one goods receipt item is required."]})

    idem_key = (data.get("idempotency_key") or "").strip() or None
    if idem_key and GoodsReceipt.objects.filter(idempotency_key=idem_key).exists():
        raise Conflict("A goods receipt with this idempotency key has already been processed.")

    po: PurchaseOrder = PurchaseOrder.objects.select_for_update().get(pk=data["purchase_order"].pk)
    if po.status not in RECEIVABLE_PO_STATUSES:
        raise ValidationError(
            {"purchase_order": f"Purchase order {po.po_number} is {po.status} and cannot receive goods."}
        )

    receipt_number = (data.get("receipt_number") or "").strip().upper()
    if not receipt_number:
        receipt_number = next_document_number("GRN", GoodsReceipt, "receipt_number")
    elif GoodsReceipt.objects.filter(receipt_number__iexact=receipt_number).exists():
        raise ValidationError({"receipt_number": ["This receipt number is already used."]})

    warehouse = data["warehouse"]
    grn = GoodsReceipt.objects.create(
        receipt_number=receipt_number,
        purchase_order=po,
        warehouse=warehouse,
        status=GoodsReceipt.Status.DRAFT,
        supplier_delivery_note=(data.get("supplier_delivery_note") or "").strip(),
        idempotency_key=idem_key,
        notes=data.get("notes") or "",
        created_by=user if (user and getattr(user, "is_authenticated", False)) else None,
        updated_by=user if (user and getattr(user, "is_authenticated", False)) else None,
    )

    for row in items_list:
        po_item: PurchaseOrderItem = row["purchase_order_item"]
        if po_item.purchase_order_id != po.pk:
            raise ValidationError(
                {"items": f"PO item #{po_item.pk} does not belong to purchase order {po.po_number}."}
            )
        qty = positive_quantity(row.get("quantity_received"), "quantity_received")
        item_warehouse = row.get("warehouse") or warehouse
        GoodsReceiptItem.objects.create(
            goods_receipt=grn,
            purchase_order_item=po_item,
            component=po_item.component,
            warehouse=item_warehouse,
            location=row.get("location"),
            lot_batch=(row.get("lot_batch") or "").strip(),
            quantity_received=qty,
            unit_cost_snapshot=po_item.unit_price,
            currency_snapshot=po.currency,
            exchange_rate_snapshot=po.exchange_rate,
            notes=(row.get("notes") or "")[:300],
        )

    if post_immediately:
        return post_goods_receipt(grn, user=user, request=request)

    audit.record_create(grn, request=request, user=user)
    return grn


@transaction.atomic
def post_goods_receipt(grn: GoodsReceipt, *, user=None, request=None) -> GoodsReceipt:
    """Atomically post ``grn``, incrementing inventory balances and updating PO received quantities."""
    grn = GoodsReceipt.objects.select_for_update().get(pk=grn.pk)
    if grn.status == GoodsReceipt.Status.POSTED:
        raise Conflict(f"Goods receipt {grn.receipt_number} has already been posted.")

    po = PurchaseOrder.objects.select_for_update().get(pk=grn.purchase_order_id)
    if po.status not in RECEIVABLE_PO_STATUSES:
        raise ValidationError(
            {"purchase_order": f"Purchase order {po.po_number} is in status {po.status} and cannot receive goods."}
        )

    grn_items = list(
        grn.items.select_related("component", "warehouse", "location").order_by("id")
    )
    if not grn_items:
        raise ValidationError({"items": "Cannot post an empty goods receipt."})

    po_item_ids = sorted({gi.purchase_order_item_id for gi in grn_items})
    locked_po_items = {
        poi.pk: poi
        for poi in PurchaseOrderItem.objects.select_for_update().filter(pk__in=po_item_ids).order_by("pk")
    }

    # Check cumulative quantities per PO line before touching inventory.
    incoming_by_po_item: dict[int, Decimal] = defaultdict(lambda: ZERO)
    for gi in grn_items:
        poi = locked_po_items[gi.purchase_order_item_id]
        if poi.purchase_order_id != po.pk:
            raise ValidationError({"items": f"Line item #{poi.pk} does not belong to {po.po_number}."})
        incoming_by_po_item[poi.pk] += gi.quantity_received

    for poi_id, total_incoming in incoming_by_po_item.items():
        poi = locked_po_items[poi_id]
        outstanding = poi.quantity_ordered - poi.quantity_received
        if total_incoming > outstanding:
            raise ValidationError(
                {
                    "quantity_received": (
                        f"Over-receipt rejected for {poi.component.internal_part_number}: "
                        f"attempting to receive {total_incoming}, but only {outstanding} remains outstanding on {po.po_number}."
                    )
                }
            )

    # Post each line to Phase 3 inventory inside the same DB transaction.
    for gi in grn_items:
        poi = locked_po_items[gi.purchase_order_item_id]
        txn, _inv_item = receive_stock(
            Movement(
                component=gi.component,
                warehouse=gi.warehouse,
                location=gi.location,
                quantity=gi.quantity_received,
                lot_batch=gi.lot_batch,
                unit_cost=gi.unit_cost_snapshot,
                currency=gi.currency_snapshot,
                source_type=StockTransaction.SourceType.GOODS_RECEIPT,
                source_id=str(grn.pk),
                reference=f"{grn.receipt_number} / {po.po_number}",
                reason=f"Goods receipt {grn.receipt_number} against {po.po_number}",
                notes=gi.notes or grn.notes,
            ),
            user=user,
            request=request,
        )
        gi.stock_transaction = txn
        gi.save(update_fields=["stock_transaction", "updated_at"])

        poi.quantity_received = (poi.quantity_received + gi.quantity_received).quantize(Decimal("0.0001"))
        poi.save(update_fields=["quantity_received", "updated_at"])

    # Lock the receipt as POSTED (after items are updated so item immutability guard allows linking txn).
    grn.status = GoodsReceipt.Status.POSTED
    grn.received_by = user if (user and getattr(user, "is_authenticated", False)) else None
    grn.received_at = timezone.now()
    if user and getattr(user, "is_authenticated", False):
        grn.updated_by = user
    grn.save(update_fields=["status", "received_by", "received_at", "updated_by", "updated_at"])

    # Advance PO status based on remaining outstanding quantities across all PO items.
    all_po_items = list(po.items.select_for_update().order_by("pk"))
    if all(item.quantity_received >= item.quantity_ordered for item in all_po_items):
        po.status = PurchaseOrder.Status.RECEIVED
    else:
        po.status = PurchaseOrder.Status.PARTIALLY_RECEIVED
    if user and getattr(user, "is_authenticated", False):
        po.updated_by = user
    po.save(update_fields=["status", "updated_by", "updated_at"])

    audit.record(
        AuditAction.PURCHASE_ORDER,
        entity_type="purchasing.goodsreceipt",
        entity_id=grn.pk,
        entity_repr=str(grn),
        new_value={
            "receipt_number": grn.receipt_number,
            "purchase_order": po.po_number,
            "po_status": po.status,
            "status": grn.status,
            "lines": len(grn_items),
        },
        user=user,
        request=request,
    )
    return grn

import concurrent.futures
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import InternalError, ProgrammingError, connection

from apps.bom.models import BOM, BOMItem, BOMRevision
from apps.components.models import Category, Component
from apps.inventory.models import InventoryItem, StockTransaction, Warehouse, WarehouseLocation
from apps.inventory.services import Movement, receive_stock
from apps.projects.models import Project
from apps.purchasing.models import GoodsReceipt, GoodsReceiptItem, PurchaseOrder, PurchaseOrderItem, PurchaseRequest
from apps.purchasing.services import create_goods_receipt
from apps.suppliers.models import Supplier, SupplierPart

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def phase4_env(make_user):
    cat = Category.objects.create(name="Passives", code="PAS")
    c1 = Component.objects.create(internal_part_number="PAS-00001", mpn="RC0603FR-0710KL", name="10k Resistor", category=cat)
    c2 = Component.objects.create(internal_part_number="PAS-00002", mpn="GRM188R71H104KA93D", name="100nF Capacitor", category=cat)

    wh = Warehouse.objects.create(code="MAIN", name="Main Warehouse")
    loc = WarehouseLocation.objects.create(warehouse=wh, code="BIN-A1", name="Bin A1")

    sup = Supplier.objects.create(code="SUP-DK", name="DigiKey", currency="USD", payment_terms="Net 30")
    sp1 = SupplierPart.objects.create(
        supplier=sup,
        component=c1,
        supplier_part_number="DK-10K",
        supplier_part_number_normalized="DK-10K",
        unit_price=Decimal("0.050000"),
        moq=Decimal("10.0000"),
        order_multiple=Decimal("10.0000"),
        is_preferred=True,
    )
    sp2 = SupplierPart.objects.create(
        supplier=sup,
        component=c2,
        supplier_part_number="DK-100NF",
        supplier_part_number_normalized="DK-100NF",
        unit_price=Decimal("0.120000"),
        moq=Decimal("1.0000"),
        order_multiple=Decimal("1.0000"),
        is_preferred=True,
    )

    admin_user = make_user("ADMIN")
    project = Project.objects.create(code="PRJ-P4", name="Phase 4 Board", created_by=admin_user)
    bom = BOM.objects.create(project=project, name="Main PCBA", created_by=admin_user)
    rev = BOMRevision.objects.create(bom=bom, revision_number="REV A", created_by=admin_user)
    BOMItem.objects.create(revision=rev, component=c1, quantity=Decimal("5.0000"), designators=["R1", "R2", "R3", "R4", "R5"])
    BOMItem.objects.create(revision=rev, component=c2, quantity=Decimal("2.0000"), designators=["C1", "C2"])

    return {
        "c1": c1,
        "c2": c2,
        "wh": wh,
        "loc": loc,
        "sup": sup,
        "sp1": sp1,
        "sp2": sp2,
        "project": project,
        "bom": bom,
        "rev": rev,
        "admin_user": admin_user,
    }


def test_pr_workflow_rbac_and_no_stock_side_effects(client_for, phase4_env):
    eng = client_for("HARDWARE_ENGINEER")
    purchase = client_for("PURCHASE")
    store = client_for("STORE")
    viewer = client_for("VIEWER")
    admin = client_for("ADMIN")

    # Viewer cannot create PR
    assert viewer.post("/api/purchasing/requests", {}, format="json").status_code == 403

    # Hardware engineer can create and submit PR
    res = eng.post(
        "/api/purchasing/requests",
        {
            "title": "Prototype Passives",
            "project": phase4_env["project"].id,
            "priority": "HIGH",
            "items": [
                {"component": phase4_env["c1"].id, "quantity": "100", "supplier_part": phase4_env["sp1"].id},
            ],
        },
        format="json",
    )
    assert res.status_code == 201
    pr_id = res.data["id"]
    assert res.data["status"] == "DRAFT"
    assert Decimal(res.data["estimated_total"]) == Decimal("5.0000")

    sub = eng.post(f"/api/purchasing/requests/{pr_id}/submit", format="json")
    assert sub.status_code == 200
    assert sub.data["status"] == "SUBMITTED"

    # Separation of duties: Engineer, Purchase, Store, Viewer CANNOT approve PR
    for client in (eng, purchase, store, viewer):
        assert client.post(f"/api/purchasing/requests/{pr_id}/approve", {}, format="json").status_code == 403

    # Admin CAN approve PR
    app = admin.post(f"/api/purchasing/requests/{pr_id}/approve", {"notes": "Approved for prototype"}, format="json")
    assert app.status_code == 200
    assert app.data["status"] == "APPROVED"

    # Items on an APPROVED PR are locked
    pr_obj = PurchaseRequest.objects.get(pk=pr_id)
    item_obj = pr_obj.items.first()
    item_obj.quantity = Decimal("999")
    with pytest.raises(ValidationError):
        item_obj.save()

    # PR creation/approval never touches inventory
    assert InventoryItem.objects.count() == 0
    assert StockTransaction.objects.count() == 0


def test_bom_shortage_to_purchase_request(client_for, phase4_env, make_user):
    store_user = make_user("STORE")
    # Put 30 pcs of c1 in stock. Build qty = 10 requires 50 pcs of c1 (shortage = 20) and 20 pcs of c2 (shortage = 20).
    receive_stock(
        Movement(component=phase4_env["c1"], warehouse=phase4_env["wh"], location=phase4_env["loc"], quantity=Decimal("30")),
        store_user,
    )

    eng = client_for("HARDWARE_ENGINEER")
    res = eng.post(
        "/api/purchasing/requests/from-bom-shortage",
        {
            "bom_revision": phase4_env["rev"].id,
            "build_quantity": "10",
            "priority": "URGENT",
        },
        format="json",
    )
    assert res.status_code == 201
    items = {i["component"]: i for i in res.data["items"]}
    assert len(items) == 2
    assert Decimal(str(items[phase4_env["c1"].id]["quantity"])) == Decimal("20.0000")
    assert Decimal(str(items[phase4_env["c2"].id]["quantity"])) == Decimal("20.0000")
    assert items[phase4_env["c1"].id]["preferred_supplier"] == phase4_env["sup"].id

    # If stock covers full build quantity (e.g. build_quantity=1 needs 5 of c1 and 2 of c2; receive 5 of c2):
    receive_stock(
        Movement(component=phase4_env["c2"], warehouse=phase4_env["wh"], location=phase4_env["loc"], quantity=Decimal("5")),
        store_user,
    )
    no_shortage = eng.post(
        "/api/purchasing/requests/from-bom-shortage",
        {"bom_revision": phase4_env["rev"].id, "build_quantity": "1"},
        format="json",
    )
    assert no_shortage.status_code == 400


def test_po_lifecycle_decimal_totals_and_immutability(client_for, phase4_env):
    purchase = client_for("PURCHASE")
    admin = client_for("ADMIN")

    # Create PR -> Approve -> Convert to PO
    pr_res = purchase.post(
        "/api/purchasing/requests",
        {
            "title": "Restock Passives",
            "items": [
                {"component": phase4_env["c1"].id, "quantity": "200", "supplier_part": phase4_env["sp1"].id},
                {"component": phase4_env["c2"].id, "quantity": "50", "supplier_part": phase4_env["sp2"].id},
            ],
        },
        format="json",
    )
    pr_id = pr_res.data["id"]
    admin.post(f"/api/purchasing/requests/{pr_id}/approve", {}, format="json")

    po_res = purchase.post(
        f"/api/purchasing/requests/{pr_id}/create-po",
        {
            "supplier": phase4_env["sup"].id,
            "default_warehouse": phase4_env["wh"].id,
            "currency": "USD",
            "exchange_rate": "1.000000",
        },
        format="json",
    )
    assert po_res.status_code == 201
    po_id = po_res.data["id"]
    # 200 * 0.05 = 10.0000; 50 * 0.12 = 6.0000 -> subtotal = 16.0000
    assert Decimal(str(po_res.data["subtotal"])) == Decimal("16.0000")
    assert Decimal(str(po_res.data["total_amount"])) == Decimal("16.0000")

    # Update tax/shipping/discount on DRAFT PO
    upd = purchase.patch(
        f"/api/purchasing/orders/{po_id}",
        {"tax_amount": "1.6000", "shipping_amount": "5.0000", "discount_amount": "0.6000"},
        format="json",
    )
    assert upd.status_code == 200
    assert Decimal(str(upd.data["total_amount"])) == Decimal("22.0000")

    # Purchase role CANNOT approve PO (requires purchase.approve)
    assert purchase.post(f"/api/purchasing/orders/{po_id}/approve", format="json").status_code == 403

    # Admin approves PO -> Purchase sends PO
    assert admin.post(f"/api/purchasing/orders/{po_id}/approve", format="json").status_code == 200
    sent = purchase.post(f"/api/purchasing/orders/{po_id}/send", format="json")
    assert sent.status_code == 200
    assert sent.data["status"] == "SENT"

    # Approving and sending PO NEVER changes inventory balances
    assert InventoryItem.objects.count() == 0
    assert StockTransaction.objects.count() == 0

    # Commercial terms and line items on SENT PO are locked
    locked_patch = purchase.patch(f"/api/purchasing/orders/{po_id}", {"tax_amount": "99.0000"}, format="json")
    assert locked_patch.status_code == 400
    poi = PurchaseOrderItem.objects.filter(purchase_order_id=po_id).first()
    poi.unit_price = Decimal("9.99")
    with pytest.raises(ValidationError):
        poi.save()
    with pytest.raises(ValidationError):
        poi.delete()

    # Supplier with open PO cannot be deleted
    assert admin.delete(f"/api/suppliers/{phase4_env['sup'].id}").status_code == 409


def test_partial_and_full_goods_receipts_and_over_receipt_rejection(client_for, phase4_env):
    purchase = client_for("PURCHASE")
    admin = client_for("ADMIN")
    store = client_for("STORE")

    po_res = purchase.post(
        "/api/purchasing/orders",
        {
            "supplier": phase4_env["sup"].id,
            "default_warehouse": phase4_env["wh"].id,
            "currency": "USD",
            "items": [
                {"component": phase4_env["c1"].id, "quantity_ordered": "100", "unit_price": "0.050000"},
            ],
        },
        format="json",
    )
    assert po_res.status_code == 201
    po_id = po_res.data["id"]
    poi_id = po_res.data["items"][0]["id"]

    # Cannot receive against DRAFT PO
    draft_grn = store.post(
        f"/api/purchasing/orders/{po_id}/receive",
        {
            "warehouse": phase4_env["wh"].id,
            "items": [{"purchase_order_item": poi_id, "quantity_received": "40"}],
        },
        format="json",
    )
    assert draft_grn.status_code == 400

    admin.post(f"/api/purchasing/orders/{po_id}/approve", format="json")
    purchase.post(f"/api/purchasing/orders/{po_id}/send", format="json")

    # Purchase role cannot receive goods (separation of duties: requires purchase.receive)
    assert (
        purchase.post(
            f"/api/purchasing/orders/{po_id}/receive",
            {"warehouse": phase4_env["wh"].id, "items": [{"purchase_order_item": poi_id, "quantity_received": "40"}]},
            format="json",
        ).status_code
        == 403
    )

    # Store role posts partial receipt of 40 pcs
    grn1 = store.post(
        f"/api/purchasing/orders/{po_id}/receive",
        {
            "warehouse": phase4_env["wh"].id,
            "supplier_delivery_note": "DN-001",
            "idempotency_key": "idem-grn-001",
            "items": [
                {
                    "purchase_order_item": poi_id,
                    "location": phase4_env["loc"].id,
                    "lot_batch": "LOT-2026A",
                    "quantity_received": "40",
                }
            ],
        },
        format="json",
    )
    assert grn1.status_code == 201
    assert grn1.data["status"] == "POSTED"

    po = PurchaseOrder.objects.get(pk=po_id)
    assert po.status == PurchaseOrder.Status.PARTIALLY_RECEIVED
    poi = PurchaseOrderItem.objects.get(pk=poi_id)
    assert poi.quantity_received == Decimal("40.0000")

    inv = InventoryItem.objects.get(component=phase4_env["c1"], warehouse=phase4_env["wh"], location=phase4_env["loc"], lot_batch="LOT-2026A")
    assert inv.quantity_on_hand == Decimal("40.0000")
    txn = StockTransaction.objects.get(pk=grn1.data["items"][0]["stock_transaction"])
    assert txn.transaction_type == StockTransaction.TransactionType.RECEIPT
    assert txn.source_type == StockTransaction.SourceType.GOODS_RECEIPT
    assert txn.unit_cost == Decimal("0.050000")
    assert txn.currency == "USD"

    # Duplicate idempotency_key is rejected with 409 Conflict and does not double-count stock
    dup_grn = store.post(
        f"/api/purchasing/orders/{po_id}/receive",
        {
            "warehouse": phase4_env["wh"].id,
            "idempotency_key": "idem-grn-001",
            "items": [{"purchase_order_item": poi_id, "quantity_received": "40"}],
        },
        format="json",
    )
    assert dup_grn.status_code == 409
    inv.refresh_from_db()
    assert inv.quantity_on_hand == Decimal("40.0000")

    # Over-receipt (70 > 60 outstanding) is rejected with 400 and leaves stock unchanged
    over_grn = store.post(
        f"/api/purchasing/orders/{po_id}/receive",
        {
            "warehouse": phase4_env["wh"].id,
            "items": [{"purchase_order_item": poi_id, "quantity_received": "70"}],
        },
        format="json",
    )
    assert over_grn.status_code == 400
    inv.refresh_from_db()
    assert inv.quantity_on_hand == Decimal("40.0000")

    # Cannot cancel a PARTIALLY_RECEIVED PO
    assert purchase.post(f"/api/purchasing/orders/{po_id}/cancel", format="json").status_code == 409

    # Receive remaining 60 pcs -> PO transitions to RECEIVED
    grn2 = store.post(
        f"/api/purchasing/orders/{po_id}/receive",
        {
            "warehouse": phase4_env["wh"].id,
            "items": [
                {
                    "purchase_order_item": poi_id,
                    "location": phase4_env["loc"].id,
                    "lot_batch": "LOT-2026A",
                    "quantity_received": "60",
                }
            ],
        },
        format="json",
    )
    assert grn2.status_code == 201
    po.refresh_from_db()
    assert po.status == PurchaseOrder.Status.RECEIVED
    inv.refresh_from_db()
    assert inv.quantity_on_hand == Decimal("100.0000")

    # Posted GoodsReceipt and GoodsReceiptItem are immutable in Python and PostgreSQL
    grn_obj = GoodsReceipt.objects.get(pk=grn1.data["id"])
    grn_obj.notes = "tampered"
    with pytest.raises(ValidationError):
        grn_obj.save()
    with pytest.raises(ValidationError):
        grn_obj.delete()
    with pytest.raises((InternalError, ProgrammingError)):
        with connection.cursor() as cur:
            cur.execute("DELETE FROM purchasing_goodsreceipt WHERE id = %s", [grn_obj.id])

    gi_obj = GoodsReceiptItem.objects.filter(goods_receipt=grn_obj).first()
    gi_obj.quantity_received = Decimal("1.0000")
    with pytest.raises(ValidationError):
        gi_obj.save()
    with pytest.raises((InternalError, ProgrammingError)):
        with connection.cursor() as cur:
            cur.execute("UPDATE purchasing_goodsreceiptitem SET quantity_received = 1 WHERE id = %s", [gi_obj.id])


def test_concurrent_goods_receipts_prevent_over_receipt(phase4_env, make_user):
    store_user = make_user("STORE")
    po = PurchaseOrder.objects.create(
        po_number="PO-CONC-01",
        supplier=phase4_env["sup"],
        default_warehouse=phase4_env["wh"],
        status=PurchaseOrder.Status.DRAFT,
        currency="USD",
        created_by=phase4_env["admin_user"],
    )
    poi = PurchaseOrderItem.objects.create(
        purchase_order=po,
        component=phase4_env["c1"],
        quantity_ordered=Decimal("100.0000"),
        unit_price=Decimal("0.050000"),
        line_total=Decimal("5.0000"),
    )
    po.status = PurchaseOrder.Status.SENT
    po.save(update_fields=["status"])

    # Two concurrent workers each attempt to receive 60 pcs against a 100-pc PO line.
    def worker():
        try:
            create_goods_receipt(
                data={"purchase_order": po, "warehouse": phase4_env["wh"]},
                items=[{"purchase_order_item": poi, "location": phase4_env["loc"], "quantity_received": Decimal("60")}],
                post_immediately=True,
                user=store_user,
            )
            return "OK"
        except Exception:
            return "ERR"
        finally:
            connection.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        results = [f.result() for f in [ex.submit(worker), ex.submit(worker)]]

    assert sorted(results) == ["ERR", "OK"]
    poi.refresh_from_db()
    assert poi.quantity_received == Decimal("60.0000")
    inv = InventoryItem.objects.get(component=phase4_env["c1"], warehouse=phase4_env["wh"], location=phase4_env["loc"])
    assert inv.quantity_on_hand == Decimal("60.0000")


def test_goods_receipt_rolls_back_atomically_when_inventory_fails(client_for, phase4_env):
    store = client_for("STORE")
    other_wh = Warehouse.objects.create(code="OTHER", name="Other Warehouse")

    po = PurchaseOrder.objects.create(
        po_number="PO-ATOMIC-01",
        supplier=phase4_env["sup"],
        default_warehouse=phase4_env["wh"],
        status=PurchaseOrder.Status.DRAFT,
        currency="USD",
        created_by=phase4_env["admin_user"],
    )
    poi = PurchaseOrderItem.objects.create(
        purchase_order=po,
        component=phase4_env["c1"],
        quantity_ordered=Decimal("50.0000"),
        unit_price=Decimal("0.050000"),
        line_total=Decimal("2.5000"),
    )
    po.status = PurchaseOrder.Status.SENT
    po.save(update_fields=["status"])

    # Pass a location belonging to MAIN warehouse while receiving into OTHER warehouse -> receive_stock raises InventoryError
    res = store.post(
        f"/api/purchasing/orders/{po.id}/receive",
        {
            "warehouse": other_wh.id,
            "items": [
                {
                    "purchase_order_item": poi.id,
                    "warehouse": other_wh.id,
                    "location": phase4_env["loc"].id,
                    "quantity_received": "25",
                }
            ],
        },
        format="json",
    )
    assert res.status_code == 400
    assert GoodsReceipt.objects.filter(purchase_order=po).count() == 0
    poi.refresh_from_db()
    assert poi.quantity_received == Decimal("0.0000")
    assert InventoryItem.objects.count() == 0

import concurrent.futures
from decimal import Decimal

import pytest
from django.db import IntegrityError, connection
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.components.models import Category, Component
from apps.inventory.models import InventoryItem, StockReservation, StockTransaction, Warehouse, WarehouseLocation
from apps.inventory.services import Movement, receive_stock

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def test_data():
    cat = Category.objects.create(name="Resistors")
    comp = Component.objects.create(mpn="RES-10K", internal_part_number="IPN-01", category=cat)
    warehouse = Warehouse.objects.create(code="WH-1", name="Main Warehouse")
    location = WarehouseLocation.objects.create(warehouse=warehouse, code="A1", name="Rack A1")
    return {"comp": comp, "wh": warehouse, "loc": location}


def test_warehouse_crud(client_for):
    admin = client_for("ADMIN")
    res = admin.post("/api/inventory/warehouses/", {"code": "WH2", "name": "Secondary"})
    assert res.status_code == 201
    assert Warehouse.objects.count() == 1


def test_zero_negative_quantities_receive(client_for, test_data):
    store = client_for("STORE")
    for q in [0, -5, "abc", "NaN", "Infinity", ""]:
        res = store.post(
            "/api/inventory/operations/receive/",
            {
                "component": test_data["comp"].id,
                "warehouse": test_data["wh"].id,
                "quantity": q,
            },
            format="json",
        )
        assert res.status_code == 400
        assert "quantity" in res.data


def test_location_mismatch(client_for, test_data):
    wh2 = Warehouse.objects.create(code="WH-2", name="Secondary")
    store = client_for("STORE")
    res = store.post(
        "/api/inventory/operations/receive/",
        {
            "component": test_data["comp"].id,
            "warehouse": wh2.id,
            "location": test_data["loc"].id,
            "quantity": 10,
        },
        format="json",
    )
    assert res.status_code == 400
    assert "location" in res.data


def test_rbac_inventory(client_for, test_data, make_user):
    anon = APIClient()
    assert anon.post("/api/inventory/operations/receive/").status_code == 403

    viewer = client_for("VIEWER")
    assert viewer.post("/api/inventory/operations/receive/").status_code == 403

    store = client_for("STORE")
    res = store.post(
        "/api/inventory/operations/receive/",
        {
            "component": test_data["comp"].id,
            "warehouse": test_data["wh"].id,
            "quantity": 100,
        },
        format="json",
    )
    assert res.status_code == 201

    res = viewer.get("/api/inventory/stock/")
    assert res.status_code == 200

    # Viewer can't view transactions
    assert viewer.get("/api/inventory/transactions/").status_code == 403
    # Production CAN view transactions (and issue)
    prod = client_for("PRODUCTION")
    assert prod.get("/api/inventory/transactions/").status_code == 200


def test_concurrent_receipt(test_data, make_user):
    user = make_user("STORE")
    def run_receipt():
        m = Movement(
            component=test_data["comp"],
            warehouse=test_data["wh"],
            location=None,
            quantity=10,
        )
        receive_stock(m, user)

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(run_receipt) for _ in range(4)]
        concurrent.futures.wait(futures)
        for f in futures:
            f.result()  # raise if failed

    assert InventoryItem.objects.count() == 1
    item = InventoryItem.objects.first()
    assert item.quantity_on_hand == 40


def test_issue_beyond_available(client_for, test_data, make_user):
    user = make_user("STORE")
    receive_stock(
        Movement(component=test_data["comp"], warehouse=test_data["wh"], location=test_data["loc"], quantity=50),
        user
    )

    store = client_for("STORE")
    res = store.post(
        "/api/inventory/operations/issue/",
        {
            "component": test_data["comp"].id,
            "warehouse": test_data["wh"].id,
            "location": test_data["loc"].id,
            "quantity": 60,
        },
        format="json",
    )
    assert res.status_code == 400
    assert "quantity" in res.data


def test_reservation_lifecycle(client_for, test_data, make_user):
    user = make_user("STORE")
    receive_stock(
        Movement(component=test_data["comp"], warehouse=test_data["wh"], location=test_data["loc"], quantity=100),
        user
    )

    store = client_for("STORE")
    res = store.post(
        "/api/inventory/operations/reserve/",
        {
            "component": test_data["comp"].id,
            "warehouse": test_data["wh"].id,
            "location": test_data["loc"].id,
            "quantity": 30,
        },
        format="json",
    )
    assert res.status_code == 201
    res_id = res.data["id"]

    item = InventoryItem.objects.first()
    assert item.quantity_on_hand == 100
    assert item.quantity_reserved == 30
    assert item.quantity_available == 70

    res = store.post(f"/api/inventory/reservations/{res_id}/release/")
    assert res.status_code == 200

    item.refresh_from_db()
    assert item.quantity_on_hand == 100
    assert item.quantity_reserved == 0

    res = store.post(f"/api/inventory/reservations/{res_id}/cancel/")
    assert res.status_code == 400


def test_ledger_immutability(test_data, make_user):
    user = make_user("STORE")
    receive_stock(
        Movement(component=test_data["comp"], warehouse=test_data["wh"], location=test_data["loc"], quantity=50),
        user
    )
    txn = StockTransaction.objects.first()

    with pytest.raises(Exception):
        txn.quantity = 100
        txn.save()

    with pytest.raises(Exception):
        txn.delete()

    with pytest.raises(Exception):
        StockTransaction.objects.all().delete()

    with pytest.raises(Exception):
        StockTransaction.objects.all().update(quantity=100)

    # Check postgres trigger
    with pytest.raises(IntegrityError):
        with connection.cursor() as cursor:
            cursor.execute("UPDATE inventory_stocktransaction SET quantity = 100")


def test_adjust_form_encoded(client_for, test_data, make_user):
    user = make_user("STORE")
    receive_stock(
        Movement(component=test_data["comp"], warehouse=test_data["wh"], location=test_data["loc"], quantity=50),
        user
    )
    store = client_for("STORE")
    res = store.post(
        "/api/inventory/operations/adjust/",
        data={
            "component": test_data["comp"].id,
            "warehouse": test_data["wh"].id,
            "location": test_data["loc"].id,
            "quantity": "10",
            "direction": "IN",
            "reason": "Found some",
        },
        format="multipart",
    )
    assert res.status_code == 201

    item = InventoryItem.objects.first()
    assert item.quantity_on_hand == 60


def test_summary_and_low_stock(client_for, test_data, make_user):
    user = make_user("STORE")
    receive_stock(
        Movement(component=test_data["comp"], warehouse=test_data["wh"], location=test_data["loc"], quantity=5),
        user
    )
    store = client_for("STORE")

    res = store.patch(
        f"/api/inventory/stock/{InventoryItem.objects.first().id}/levels/",
        {"minimum_stock": 10},
        format="json",
    )
    assert res.status_code == 200

    res = store.get("/api/inventory/stock/summary/")
    assert res.status_code == 200
    assert res.data["total_on_hand"] == Decimal("5.0000")
    assert res.data["low_stock"] == 1


def test_warehouse_delete_refused(client_for, test_data, make_user):
    user = make_user("STORE")
    receive_stock(
        Movement(component=test_data["comp"], warehouse=test_data["wh"], location=test_data["loc"], quantity=50),
        user
    )
    admin = client_for("ADMIN")
    res = admin.delete(f"/api/inventory/warehouses/{test_data['wh'].id}/")
    assert res.status_code == 409
    assert "still holds stock" in str(res.data)

    res = admin.delete(f"/api/inventory/locations/{test_data['loc'].id}/")
    assert res.status_code == 409

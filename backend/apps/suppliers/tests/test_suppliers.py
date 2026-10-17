from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import InternalError, ProgrammingError, connection

from apps.components.models import Category, Component
from apps.suppliers.models import Supplier, SupplierPart, SupplierPriceHistory

pytestmark = pytest.mark.django_db


@pytest.fixture
def comp(db):
    cat = Category.objects.create(name="Microcontrollers", code="MCU")
    return Component.objects.create(
        internal_part_number="MCU-00001",
        mpn="STM32F405RGT6",
        name="ARM Cortex-M4 MCU",
        category=cat,
    )


def test_supplier_crud_and_rbac(client_for):
    viewer = client_for("VIEWER")
    purchase = client_for("PURCHASE")
    admin = client_for("ADMIN")

    # Viewer cannot create supplier
    assert viewer.post("/api/suppliers", {"name": "DigiKey"}, format="json").status_code == 403

    # Purchase role can create and edit supplier
    res = purchase.post(
        "/api/suppliers",
        {
            "name": "DigiKey Electronics",
            "country": "United States",
            "currency": "usd",
            "lead_time_days": 5,
            "rating": 5,
        },
        format="json",
    )
    assert res.status_code == 201
    sup_id = res.data["id"]
    assert res.data["code"] == "SUP-0001"
    assert res.data["currency"] == "USD"

    # Viewer can list and retrieve
    assert viewer.get("/api/suppliers").status_code == 200
    assert viewer.get(f"/api/suppliers/{sup_id}").status_code == 200

    # Add contact
    c_res = purchase.post(
        f"/api/suppliers/{sup_id}/contacts",
        {"name": "Alice Rep", "email": "alice@digikey.example", "is_primary": True},
        format="json",
    )
    assert c_res.status_code == 201
    contact_id = c_res.data["id"]

    c_res2 = purchase.post(
        f"/api/suppliers/{sup_id}/contacts",
        {"name": "Bob Rep", "email": "bob@digikey.example", "is_primary": True},
        format="json",
    )
    assert c_res2.status_code == 201
    detail = viewer.get(f"/api/suppliers/{sup_id}").data
    primaries = [c for c in detail["contacts"] if c["is_primary"]]
    assert len(primaries) == 1 and primaries[0]["name"] == "Bob Rep"

    # Remove first contact
    assert purchase.delete(f"/api/suppliers/{sup_id}/contacts/{contact_id}").status_code == 204

    # Purchase role cannot delete supplier (requires supplier.delete)
    assert purchase.delete(f"/api/suppliers/{sup_id}").status_code == 403
    assert admin.delete(f"/api/suppliers/{sup_id}").status_code == 204
    assert Supplier.objects.count() == 0
    assert Supplier.all_objects.count() == 1


def test_supplier_part_price_breaks_comparison_and_search(client_for, comp):
    purchase = client_for("PURCHASE")
    s1 = Supplier.objects.create(code="DK", name="DigiKey", currency="USD", lead_time_days=4)
    s2 = Supplier.objects.create(code="MOU", name="Mouser", currency="USD", lead_time_days=7)

    # Create SupplierPart with price breaks
    res1 = purchase.post(
        "/api/supplier-parts",
        {
            "supplier": s1.id,
            "component": comp.id,
            "supplier_part_number": " 497-11767-1-ND ",
            "unit_price": "8.500000",
            "moq": "1",
            "order_multiple": "1",
            "is_preferred": True,
            "price_breaks": [
                {"min_quantity": "10", "unit_price": "7.800000"},
                {"min_quantity": "100", "unit_price": "6.500000"},
            ],
        },
        format="json",
    )
    assert res1.status_code == 201
    part1_id = res1.data["id"]

    # Duplicate normalized SPN on same supplier is rejected
    dup = purchase.post(
        "/api/supplier-parts",
        {
            "supplier": s1.id,
            "component": comp.id,
            "supplier_part_number": "497-11767-1-nd",
            "unit_price": "8.500000",
        },
        format="json",
    )
    assert dup.status_code == 400

    # Create second supplier offer with MOQ=10 and order_multiple=5
    res2 = purchase.post(
        "/api/supplier-parts",
        {
            "supplier": s2.id,
            "component": comp.id,
            "supplier_part_number": "511-STM32F405RGT6",
            "unit_price": "7.200000",
            "moq": "10",
            "order_multiple": "5",
            "is_preferred": False,
        },
        format="json",
    )
    assert res2.status_code == 201

    # Component search_document now indexes the supplier part number
    comp.refresh_from_db()
    assert "497-11767-1-ND" in comp.search_document
    assert "DigiKey" in comp.search_document

    # Compare at quantity=12
    cmp_res = purchase.get(f"/api/supplier-parts/compare?component={comp.id}&quantity=12")
    assert cmp_res.status_code == 200
    offers = cmp_res.data["offers"]
    assert len(offers) == 2
    # Preferred supplier is sorted first; at qty=12 its 10+ break (7.80) applies
    assert offers[0]["supplier_code"] == "DK"
    assert Decimal(str(offers[0]["effective_unit_price"])) == Decimal("7.800000")
    assert Decimal(str(offers[0]["effective_order_quantity"])) == Decimal("12.0000")
    # Mouser has order_multiple=5 and MOQ=10, so qty=12 rounds up to 15
    assert offers[1]["supplier_code"] == "MOU"
    assert Decimal(str(offers[1]["effective_order_quantity"])) == Decimal("15.0000")


def test_supplier_price_history_immutability(client_for, comp):
    purchase = client_for("PURCHASE")
    sup = Supplier.objects.create(code="FAR", name="Farnell")
    res = purchase.post(
        "/api/supplier-parts",
        {
            "supplier": sup.id,
            "component": comp.id,
            "supplier_part_number": "FAR-100",
            "unit_price": "1.250000",
        },
        format="json",
    )
    assert res.status_code == 201
    part_id = res.data["id"]

    # Update unit price -> appends to history
    upd = purchase.patch(f"/api/supplier-parts/{part_id}", {"unit_price": "1.100000"}, format="json")
    assert upd.status_code == 200

    hist_res = purchase.get(f"/api/supplier-parts/{part_id}/price-history")
    assert hist_res.status_code == 200
    assert len(hist_res.data) == 2

    hist = SupplierPriceHistory.objects.first()
    hist.unit_price = Decimal("9.990000")
    with pytest.raises(ValidationError):
        hist.save()
    with pytest.raises(ValidationError):
        hist.delete()
    with pytest.raises(ValidationError):
        SupplierPriceHistory.objects.all().update(unit_price=Decimal("9.990000"))
    with pytest.raises(ValidationError):
        SupplierPriceHistory.objects.all().delete()

    # DB-level trigger blocks raw SQL UPDATE and DELETE
    with pytest.raises((InternalError, ProgrammingError)):
        with connection.cursor() as cur:
            cur.execute("UPDATE suppliers_supplierpricehistory SET unit_price = 5.0 WHERE id = %s", [hist.id])

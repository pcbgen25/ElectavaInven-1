import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from apps.inventory.models import Warehouse, WarehouseLocation, InventoryItem, StockTransaction, StockReservation
from apps.components.models import Component, Category
from apps.accounts.models import User
from decimal import Decimal

@pytest.fixture
def auth_client():
    user = User.objects.create_superuser(email="admin@test.com", password="password", first_name="admin", last_name="admin")
    client = APIClient()
    client.force_authenticate(user=user)
    return client, user

@pytest.fixture
def test_data(auth_client):
    user = auth_client[1]
    cat = Category.objects.create(name="Resistors")
    comp = Component.objects.create(mpn="RES-10K", internal_part_number="IPN-01", category=cat)
    warehouse = Warehouse.objects.create(code="WH-1", name="Main Warehouse")
    location = WarehouseLocation.objects.create(warehouse=warehouse, code="A1", name="Rack A1")
    return {"user": user, "comp": comp, "wh": warehouse, "loc": location}

@pytest.mark.django_db
def test_warehouse_crud(auth_client):
    client = auth_client[0]
    res = client.post('/api/inventory/warehouses/', {'code': 'WH2', 'name': 'Secondary'})
    assert res.status_code == 201, res.data
    assert Warehouse.objects.count() == 1

@pytest.mark.django_db
def test_stock_receipt(auth_client, test_data):
    client = auth_client[0]
    payload = {
        'component_id': str(test_data['comp'].id),
        'warehouse_id': str(test_data['wh'].id),
            'location_id': str(test_data['loc'].id),
        'location_id': str(test_data['loc'].id),
        'quantity': 100,
        'reason': 'Initial Stock'
    }
    res = client.post('/api/inventory/operations/receive/', payload)
    assert res.status_code == 201, res.data
    
    item = InventoryItem.objects.first()
    assert item.quantity_on_hand == 100
    assert item.quantity_available == 100

    txn = StockTransaction.objects.first()
    assert txn.transaction_type == "RECEIPT"
    assert txn.quantity == 100

@pytest.mark.django_db
def test_prevent_issue_beyond_available(auth_client, test_data):
    client, user = auth_client
    from apps.inventory.services import execute_stock_operation
    execute_stock_operation("RECEIPT", test_data['comp'], test_data['wh'], test_data['loc'], 50, user)
    
    payload = {
        'component_id': str(test_data['comp'].id),
        'warehouse_id': str(test_data['wh'].id),
            'location_id': str(test_data['loc'].id),
        'location_id': str(test_data['loc'].id),
        'quantity': 60
    }
    res = client.post('/api/inventory/operations/issue/', payload)
    assert res.status_code == 400, res.data
    assert "Insufficient available stock" in res.data['detail']

@pytest.mark.django_db
def test_stock_transfer(auth_client, test_data):
    client, user = auth_client
    wh2 = Warehouse.objects.create(code="WH-2", name="W2")
    from apps.inventory.services import execute_stock_operation
    execute_stock_operation("RECEIPT", test_data['comp'], test_data['wh'], test_data['loc'], 100, user)
    
    payload = {
        'component_id': str(test_data['comp'].id),
        'from_warehouse_id': str(test_data['wh'].id),
        'from_location_id': str(test_data['loc'].id),
        'to_warehouse_id': str(wh2.id),
        'quantity': 25
    }
    res = client.post('/api/inventory/operations/transfer/', payload)
    assert res.status_code == 200, res.data
    
    item1 = InventoryItem.objects.get(warehouse=test_data['wh'])
    assert item1.quantity_on_hand == 75
    
    item2 = InventoryItem.objects.get(warehouse=wh2)
    assert item2.quantity_on_hand == 25

@pytest.mark.django_db
def test_reservation_and_release(auth_client, test_data):
    client, user = auth_client
    from apps.inventory.services import execute_stock_operation
    execute_stock_operation("RECEIPT", test_data['comp'], test_data['wh'], test_data['loc'], 100, user)
    
    res = client.post('/api/inventory/operations/reserve/', {
        'component_id': str(test_data['comp'].id),
        'warehouse_id': str(test_data['wh'].id),
            'location_id': str(test_data['loc'].id),
        'quantity': 30
    })
    assert res.status_code == 201, res.data
    res_id = res.data['id']
    
    item = InventoryItem.objects.get()
    assert item.quantity_on_hand == 100
    assert item.quantity_reserved == 30
    assert item.quantity_available == 70
    
    # Release
    res_release = client.post(f'/api/inventory/operations/{res_id}/release_reservation/')
    assert res_release.status_code == 200
    
    item.refresh_from_db()
    assert item.quantity_reserved == 0
    assert item.quantity_available == 100

@pytest.mark.django_db
def test_transaction_immutability(auth_client, test_data):
    client, user = auth_client
    from apps.inventory.services import execute_stock_operation
    txn, _ = execute_stock_operation("RECEIPT", test_data['comp'], test_data['wh'], test_data['loc'], 10, user)
    
    from django.core.exceptions import ValidationError
    with pytest.raises(ValidationError):
        txn.quantity = 20
        txn.save()

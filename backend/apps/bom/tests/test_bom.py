import pytest
from rest_framework.test import APIClient
from apps.projects.models import Project
from apps.bom.models import BOM, BOMRevision, BOMItem
from apps.components.models import Component, Category
from apps.accounts.models import Role
from apps.bom.services import parse_kicad_csv, compare_revisions

pytestmark = pytest.mark.django_db

@pytest.fixture
def test_data(make_user):
    user = make_user()
    role = Role.objects.create(name="Test", code="TEST")
    from apps.accounts.models import Permission
    perms = [Permission.objects.get_or_create(code=p)[0] for p in ["bom.view", "bom.create", "bom.edit", "bom.import", "bom.review", "bom.release", "bom.compare"]]
    role.permissions.set(perms)
    user.roles.add(role)
    
    project = Project.objects.create(code="BOM-PRJ", name="BOM Test", created_by=user)
    category = Category.objects.create(name="ICs")
    c1 = Component.objects.create(internal_part_number="STM32F411VET6", mpn="STM32F411VET6", category=category, created_by=user)
    c2 = Component.objects.create(internal_part_number="TCAN1042HGVDRQ1", mpn="TCAN1042HGVDRQ1", category=category, created_by=user)
    
    return user, project, c1, c2

def test_bom_creation_and_release(test_data):
    user, project, c1, c2 = test_data
    client = APIClient()
    client.force_authenticate(user=user)
    
    # Create BOM
    resp = client.post("/api/boms/", {
        "project": project.id,
        "name": "Main Board"
    })
    assert resp.status_code == 201, resp.data
    bom_id = resp.data["id"]
    
    # Create Revision
    resp = client.post("/api/bom-revisions/", {
        "bom": bom_id,
        "revision_number": "REV A"
    })
    assert resp.status_code == 201, resp.data
    rev_id = resp.data["id"]
    
    # Add Item
    resp = client.post("/api/bom-items/", {
        "revision": rev_id,
        "component": c1.id,
        "quantity": 5,
        "designators": ["U1", "U2", "U3", "U4", "U5"]
    })
    assert resp.status_code == 201, resp.data
    
    # Release Revision
    resp = client.post(f"/api/bom-revisions/{rev_id}/release/")
    assert resp.status_code == 200
    assert resp.data["status"] == "RELEASED"
    
    # Verify immutability
    resp = client.patch(f"/api/bom-revisions/{rev_id}/", {"revision_number": "REV B"})
    assert resp.status_code == 400
    assert "Cannot modify a released BOM revision" in str(resp.data)

def test_kicad_csv_parsing():
    csv_data = """Reference,Value,Footprint,Datasheet,Description,Manufacturer,MPN,Quantity\nU1,STM32F411VET6,LQFP-100,,MCU,,STM32F411VET6,1\n"R1, R2",10k,0402,,Resistor,,RC0402FR-0710KL,2\n"""
    items = parse_kicad_csv(csv_data)
    assert len(items) == 2
    assert items[0]["mpn"] == "STM32F411VET6"
    assert items[0]["quantity"] == 1
    assert items[1]["designators"] == ["R1", "R2"]
    assert items[1]["quantity"] == 2

def test_bom_comparison(test_data):
    user, project, c1, c2 = test_data
    bom = BOM.objects.create(project=project, name="Diff Test", created_by=user)
    
    rev_a = BOMRevision.objects.create(bom=bom, revision_number="A", created_by=user)
    BOMItem.objects.create(revision=rev_a, component=c1, quantity=1, designators=["U1"])
    BOMItem.objects.create(revision=rev_a, component=c2, quantity=2, designators=["U2", "U3"])
    
    rev_b = BOMRevision.objects.create(bom=bom, revision_number="B", created_by=user)
    BOMItem.objects.create(revision=rev_b, component=c1, quantity=2, designators=["U1", "U4"]) # Qty Changed
    # c2 is removed
    
    diffs = compare_revisions(rev_a, rev_b)
    
    for diff in diffs:
        if diff["component_id"] == c1.id:
            assert diff["status"] == "QUANTITY CHANGED"
        if diff["component_id"] == c2.id:
            assert diff["status"] == "REMOVED"

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.bom.models import BOM, BOMRevision, BOMItem

pytestmark = pytest.mark.django_db


from apps.components.models import Component, Category
from apps.projects.models import Project

@pytest.fixture
def test_data(make_user):
    user = make_user("HARDWARE_ENGINEER")
    project = Project.objects.create(name="Proj", code="PRJ")
    cat = Category.objects.create(name="Res")
    c1 = Component.objects.create(category=cat, mpn="C1", internal_part_number="IPN-1")
    c2 = Component.objects.create(category=cat, mpn="C2", internal_part_number="IPN-2")
    return user, project, c1, c2

def test_released_revision_immutability(client_for, test_data):
    user, project, c1, c2 = test_data
    eng = client_for("HARDWARE_ENGINEER", user=user)

    # 1. Create a BOM and release the revision
    bom = BOM.objects.create(project=project, name="Test BOM", created_by=user)
    rev = BOMRevision.objects.create(bom=bom, revision_name="Rev 1", created_by=user)
    BOMItem.objects.create(revision=rev, component=c1, quantity=10, designators=["R1"])

    res = eng.post(f"/api/bom-revisions/{rev.id}/release/")
    assert res.status_code == 200

    # 2. Assert PATCH on released revision is rejected
    res = eng.patch(f"/api/bom-revisions/{rev.id}/", {"revision_name": "Rev 2"})
    assert res.status_code == 400

    # 3. Assert DELETE on released revision is rejected
    res = eng.delete(f"/api/bom-revisions/{rev.id}/")
    assert res.status_code == 400

    # 4. Assert item edits are rejected
    item = rev.items.first()
    res = eng.patch(f"/api/bom-items/{item.id}/", {"quantity": 20})
    assert res.status_code == 400

    # 5. Assert item additions are rejected
    res = eng.post(
        "/api/bom-items/",
        {"revision": rev.id, "component": c2.id, "quantity": 1},
        format="json",
    )
    assert res.status_code == 400

    # 6. Assert item deletion is rejected
    res = eng.delete(f"/api/bom-items/{item.id}/")
    assert res.status_code == 400

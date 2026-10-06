import pytest
from rest_framework.test import APIClient
from apps.projects.models import Project
from apps.accounts.models import Role

pytestmark = pytest.mark.django_db

def test_project_crud(make_user):
    user = make_user()
    role = Role.objects.create(name="Test Role", code="TEST")
    from apps.accounts.models import Permission
    perms = [Permission.objects.get_or_create(code=x)[0] for x in ["project.view", "project.create", "project.edit", "project.delete", "project.manage_members"]]
    role.permissions.set(perms)
    user.roles.add(role)
    
    client = APIClient()
    client.force_authenticate(user=user)
    
    # Create
    resp = client.post("/api/projects/", {
        "code": "PRJ-01",
        "name": "Test Project",
        "status": "ACTIVE"
    })
    assert resp.status_code == 201
    project_id = resp.data["id"]
    
    # List
    resp = client.get("/api/projects/")
    assert len(resp.data["results"]) == 1
    
    # Update
    resp = client.patch(f"/api/projects/{project_id}/", {"name": "Updated PRJ"})
    assert resp.status_code == 200
    assert resp.data["name"] == "Updated PRJ"
    
    # Manage Members
    member_user = make_user()
    resp = client.post(f"/api/projects/{project_id}/members/", {
        "user": member_user.id,
        "notes": "Lead Engineer"
    })
    assert resp.status_code == 201
    
    # Delete
    resp = client.delete(f"/api/projects/{project_id}/")
    assert resp.status_code == 204
    assert Project.objects.count() == 0

def test_project_permissions(make_user):
    user = make_user()
    client = APIClient()
    client.force_authenticate(user=user)
    
    resp = client.post("/api/projects/", {"code": "PRJ-02", "name": "Fail"})
    assert resp.status_code == 403

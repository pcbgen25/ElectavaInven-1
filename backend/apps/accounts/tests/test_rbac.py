import pytest

from apps.accounts.models import Role
from apps.accounts.rbac_catalog import PERMISSIONS, ROLES
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db


def test_catalog_synced_on_migrate():
    assert Role.objects.filter(code__in=ROLES.keys()).count() == len(ROLES)
    sa = Role.objects.get(code="SUPER_ADMIN")
    assert sa.permissions.count() == len(PERMISSIONS)
    viewer = set(Role.objects.get(code="VIEWER").permissions.values_list("code", flat=True))
    assert all(code.endswith(".view") for code in viewer)


@pytest.mark.parametrize(
    "role,expected",
    [("VIEWER", 403), ("PRODUCTION", 403), ("STORE", 403), ("PCB_ENGINEER", 201), ("HARDWARE_ENGINEER", 201), ("ADMIN", 201)],
)
def test_component_create_permission_by_role(client_for, capacitor_category, role, expected):
    resp = client_for(role).post(
        "/api/components",
        {"name": "Cap", "category": capacitor_category.pk,
         "specifications": [{"definition": capacitor_category.specification_definitions.get(key="capacitance").pk, "value": "1u"}]},
        format="json",
    )
    assert resp.status_code == expected, resp.content


def test_user_without_roles_has_no_access(client_for):
    client = client_for(None)
    assert client.get("/api/components").status_code == 403
    assert client.get("/api/dashboard").status_code == 200  # dashboard is per-permission filtered
    assert client.get("/api/dashboard").data["recent_components"] == []


def test_user_management_requires_user_manage(client_for):
    assert client_for("HARDWARE_ENGINEER").get("/api/users").status_code == 403
    assert client_for("ADMIN").get("/api/users").status_code == 200


def test_admin_cannot_grant_super_admin(client_for):
    resp = client_for("ADMIN").post(
        "/api/users",
        {"email": "x@test.local", "first_name": "X", "last_name": "Y", "password": "Strong-Pass-123x",
         "role_codes": ["SUPER_ADMIN"]},
        format="json",
    )
    assert resp.status_code == 403


def test_admin_creates_user_and_role_change_is_audited(client_for):
    client = client_for("ADMIN")
    resp = client.post(
        "/api/users",
        {"email": "New.Person@Test.local", "first_name": "New", "last_name": "Person",
         "password": "Strong-Pass-123x", "role_codes": ["viewer"]},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert resp.data["email"] == "new.person@test.local"
    assert "password" not in resp.data
    uid = resp.data["id"]
    create_log = AuditLog.objects.get(action="CREATE", entity_type="accounts.user", entity_id=str(uid))
    assert create_log.new_value["password"] == "***redacted***"
    resp = client.patch(f"/api/users/{uid}", {"role_codes": ["STORE"]}, format="json")
    assert resp.status_code == 200
    change = AuditLog.objects.get(action="PERMISSION_CHANGE", entity_id=str(uid))
    assert change.old_value == {"roles": ["VIEWER"]} and change.new_value == {"roles": ["STORE"]}


def test_weak_password_rejected(client_for):
    resp = client_for("ADMIN").post(
        "/api/users",
        {"email": "w@test.local", "first_name": "W", "last_name": "P", "password": "12345678"},
        format="json",
    )
    assert resp.status_code == 400


def test_cannot_deactivate_self(make_user, client_for):
    admin = make_user("ADMIN")
    resp = client_for(user=admin).patch(f"/api/users/{admin.pk}", {"is_active": False}, format="json")
    assert resp.status_code == 400


def test_users_cannot_be_deleted(client_for, make_user):
    target = make_user("VIEWER")
    assert client_for("ADMIN").delete(f"/api/users/{target.pk}").status_code == 405


def test_role_permissions_update(client_for):
    client = client_for("SUPER_ADMIN")
    role = Role.objects.get(code="VIEWER")
    resp = client.put(f"/api/roles/{role.pk}/permissions", {"permission_codes": ["component.view"]}, format="json")
    assert resp.status_code == 200
    assert resp.data["permission_codes"] == ["component.view"]
    bad = client.put(f"/api/roles/{role.pk}/permissions", {"permission_codes": ["nope.nothing"]}, format="json")
    assert bad.status_code == 400
    sa = Role.objects.get(code="SUPER_ADMIN")
    assert client.put(f"/api/roles/{sa.pk}/permissions", {"permission_codes": []}, format="json").status_code == 400


def test_system_role_cannot_be_deleted(client_for):
    role = Role.objects.get(code="VIEWER")
    assert client_for("SUPER_ADMIN").delete(f"/api/roles/{role.pk}").status_code == 400

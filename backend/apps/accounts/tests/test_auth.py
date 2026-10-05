import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from conftest import TEST_PASSWORD

pytestmark = pytest.mark.django_db


def _csrf_client():
    client = APIClient(enforce_csrf_checks=True)
    resp = client.get("/api/auth/csrf")
    assert resp.status_code == 200
    return client, client.cookies["csrftoken"].value


def test_login_requires_csrf_token(make_user):
    user = make_user("VIEWER")
    client = APIClient(enforce_csrf_checks=True)
    resp = client.post("/api/auth/login", {"email": user.email, "password": TEST_PASSWORD}, format="json")
    assert resp.status_code == 403


def test_login_success_returns_permissions_and_sets_session(make_user):
    user = make_user("PCB_ENGINEER")
    client, token = _csrf_client()
    resp = client.post(
        "/api/auth/login", {"email": user.email.upper(), "password": TEST_PASSWORD}, format="json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert resp.status_code == 200, resp.content
    assert "component.create" in resp.data["permissions"]
    assert "user.manage" not in resp.data["permissions"]
    assert "password" not in resp.data
    assert "sessionid" in client.cookies
    assert client.cookies["sessionid"]["httponly"]
    me = client.get("/api/auth/me")
    assert me.status_code == 200 and me.data["email"] == user.email
    assert AuditLog.objects.filter(action="LOGIN", user=user).exists()


def test_login_wrong_password_generic_error_and_audited(make_user):
    user = make_user("VIEWER")
    client, token = _csrf_client()
    resp = client.post(
        "/api/auth/login", {"email": user.email, "password": "nope-nope-nope"}, format="json", HTTP_X_CSRFTOKEN=token
    )
    assert resp.status_code == 400
    assert resp.data["detail"] == "Invalid email or password."
    log = AuditLog.objects.get(action="LOGIN_FAILED")
    assert "nope" not in str(log.metadata) and "nope" not in str(log.new_value)


def test_inactive_user_cannot_login(make_user):
    user = make_user("VIEWER", is_active=False)
    client, token = _csrf_client()
    resp = client.post(
        "/api/auth/login", {"email": user.email, "password": TEST_PASSWORD}, format="json", HTTP_X_CSRFTOKEN=token
    )
    assert resp.status_code == 400


def test_login_is_rate_limited(make_user):
    user = make_user("VIEWER")
    client, token = _csrf_client()
    codes = [
        client.post(
            "/api/auth/login", {"email": user.email, "password": "wrong-password-x"}, format="json",
            HTTP_X_CSRFTOKEN=token,
        ).status_code
        for _ in range(7)
    ]
    assert codes[-1] == 429  # test settings allow 5/min


def test_unauthenticated_api_access_denied(anon_client):
    assert anon_client.get("/api/components").status_code == 403
    assert anon_client.get("/api/auth/me").status_code == 403
    assert anon_client.get("/api/dashboard").status_code == 403


def test_logout_ends_session(make_user):
    user = make_user("VIEWER")
    client, token = _csrf_client()
    client.post("/api/auth/login", {"email": user.email, "password": TEST_PASSWORD}, format="json", HTTP_X_CSRFTOKEN=token)
    token = client.cookies["csrftoken"].value  # rotated on login
    assert client.post("/api/auth/logout", HTTP_X_CSRFTOKEN=token).status_code == 204
    assert client.get("/api/auth/me").status_code == 403
    assert AuditLog.objects.filter(action="LOGOUT", user=user).exists()


def test_change_password(client_for, make_user):
    user = make_user("VIEWER")
    client = client_for(user=user)
    bad = client.post("/api/auth/change-password", {"current_password": "x", "new_password": "Another-Pass-77z"}, format="json")
    assert bad.status_code == 400
    ok = client.post(
        "/api/auth/change-password", {"current_password": TEST_PASSWORD, "new_password": "Another-Pass-77z"}, format="json"
    )
    assert ok.status_code == 204
    user.refresh_from_db()
    assert user.check_password("Another-Pass-77z")
    assert AuditLog.objects.filter(action="PASSWORD_CHANGE", entity_id=str(user.pk)).exists()

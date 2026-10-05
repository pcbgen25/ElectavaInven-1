import pytest

from apps.audit import services as audit
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db


def test_audit_log_is_append_only():
    log = audit.record("CREATE", entity_type="x.y", entity_id=1)
    log.entity_repr = "changed"
    with pytest.raises(PermissionError):
        log.save()
    with pytest.raises(PermissionError):
        log.delete()
    with pytest.raises(PermissionError):
        AuditLog.objects.all().delete()
    with pytest.raises(PermissionError):
        AuditLog.objects.all().update(action="DELETE")


def test_secrets_redacted_recursively():
    log = audit.record(
        "UPDATE", entity_type="x.y", new_value={"password": "p", "nested": {"api_key": "k", "ok": 1}, "name": "n"}
    )
    assert log.new_value == {"password": "***redacted***", "nested": {"api_key": "***redacted***", "ok": 1}, "name": "n"}


def test_audit_api_permissions(client_for):
    audit.record("CREATE", entity_type="x.y", entity_id=1)
    assert client_for("HARDWARE_ENGINEER").get("/api/audit-logs").status_code == 403
    resp = client_for("ADMIN").get("/api/audit-logs", {"entity_type": "x.y"})
    assert resp.status_code == 200 and resp.data["count"] == 1
    assert client_for("ADMIN").delete(f"/api/audit-logs/{resp.data['results'][0]['id']}").status_code == 405


def test_dashboard_metrics(client_for, capacitor_category):
    eng = client_for("HARDWARE_ENGINEER")
    d = capacitor_category.specification_definitions.get(key="capacitance")
    eng.post("/api/components", {"name": "C", "category": capacitor_category.pk, "lifecycle_status": "OBSOLETE",
                                 "specifications": [{"definition": d.pk, "value": "1u"}]}, format="json")
    data = eng.get("/api/dashboard").data
    assert data["metrics"]["total_components"]["value"] == 1
    assert data["metrics"]["obsolete_components"]["value"] == 1
    assert data["metrics"]["low_stock"] == {"value": None, "available": False, "phase": 3}
    assert data["recent_components"][0]["name"] == "C"
    assert all(a["action"] != "LOGIN" for a in data["recent_activity"])

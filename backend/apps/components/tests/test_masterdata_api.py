import pytest

from apps.components.models import Category

pytestmark = pytest.mark.django_db


def test_category_crud_and_guards(client_for, capacitor_category):
    admin = client_for("ADMIN")
    viewer = client_for("VIEWER")
    assert viewer.post("/api/categories", {"name": "X", "code": "X"}, format="json").status_code == 403
    resp = admin.post("/api/categories", {"name": "Inductors", "code": "ind", "parent": capacitor_category.parent_id},
                      format="json")
    assert resp.status_code == 201, resp.content
    assert resp.data["code"] == "IND"
    assert resp.data["full_path"] == "Passives / Inductors"
    dup = admin.post("/api/categories", {"name": "inductors", "code": "IND2", "parent": capacitor_category.parent_id},
                     format="json")
    assert dup.status_code == 400
    bad_code = admin.post("/api/categories", {"name": "Bad", "code": "bad code!"}, format="json")
    assert bad_code.status_code == 400
    # cannot delete a parent with children
    assert admin.delete(f"/api/categories/{capacitor_category.parent_id}").status_code == 409
    # cannot create cycles
    cyc = admin.patch(f"/api/categories/{capacitor_category.parent_id}", {"parent": capacitor_category.pk}, format="json")
    assert cyc.status_code == 400
    assert admin.delete(f"/api/categories/{resp.data['id']}").status_code == 204
    assert Category.all_objects.get(pk=resp.data["id"]).deleted_at is not None


def test_category_with_components_cannot_be_deleted(client_for, ic_category):
    eng = client_for("HARDWARE_ENGINEER")
    eng.post("/api/components", {"name": "Part", "category": ic_category.pk}, format="json")
    assert client_for("ADMIN").delete(f"/api/categories/{ic_category.pk}").status_code == 409


def test_effective_specification_definitions(client_for, capacitor_category):
    resp = client_for("VIEWER").get(f"/api/categories/{capacitor_category.pk}/specification-definitions")
    assert resp.status_code == 200
    assert [d["key"] for d in resp.data] == ["rohs_note", "capacitance", "dielectric"]  # ancestors first


def test_spec_definition_rules(client_for, capacitor_category):
    admin = client_for("ADMIN")
    clash = admin.post("/api/specification-definitions", {
        "category": capacitor_category.pk, "key": "rohs_note", "name": "Dup", "data_type": "STRING"}, format="json")
    assert clash.status_code == 400  # key already inherited from parent
    no_choices = admin.post("/api/specification-definitions", {
        "category": capacitor_category.pk, "key": "grade", "name": "Grade", "data_type": "ENUM"}, format="json")
    assert no_choices.status_code == 400
    si_on_text = admin.post("/api/specification-definitions", {
        "category": capacitor_category.pk, "key": "x", "name": "X", "data_type": "STRING", "use_si_prefix": True},
        format="json")
    assert si_on_text.status_code == 400
    ok = admin.post("/api/specification-definitions", {
        "category": capacitor_category.pk, "key": "esr", "name": "ESR", "data_type": "DECIMAL", "unit": "Ω",
        "use_si_prefix": True}, format="json")
    assert ok.status_code == 201, ok.content


def test_spec_definition_in_use_is_protected(client_for, capacitor_category):
    eng = client_for("HARDWARE_ENGINEER")
    admin = client_for("ADMIN")
    cap_def = capacitor_category.specification_definitions.get(key="capacitance")
    eng.post("/api/components", {"name": "C", "category": capacitor_category.pk,
                                 "specifications": [{"definition": cap_def.pk, "value": "1u"}]}, format="json")
    assert admin.patch(f"/api/specification-definitions/{cap_def.pk}", {"data_type": "STRING"}, format="json").status_code == 400
    assert admin.delete(f"/api/specification-definitions/{cap_def.pk}").status_code == 409
    assert admin.patch(f"/api/specification-definitions/{cap_def.pk}", {"is_active": False}, format="json").status_code == 200


def test_manufacturer_and_package_crud(client_for):
    admin = client_for("ADMIN")
    m = admin.post("/api/manufacturers", {"name": "Texas  Instruments", "short_name": "TI"}, format="json")
    assert m.status_code == 201 and m.data["name"] == "Texas Instruments"
    assert admin.post("/api/manufacturers", {"name": "texas instruments"}, format="json").status_code == 400
    p = admin.post("/api/packages", {"name": "SOIC-8", "mounting_type": "SMD", "pin_count": 8}, format="json")
    assert p.status_code == 201
    assert admin.post("/api/packages", {"name": "soic-8"}, format="json").status_code == 400
    assert client_for("VIEWER").get("/api/manufacturers").data["count"] == 1
    assert admin.delete(f"/api/manufacturers/{m.data['id']}").status_code == 204
    # name can be reused after soft delete
    assert admin.post("/api/manufacturers", {"name": "Texas Instruments"}, format="json").status_code == 201

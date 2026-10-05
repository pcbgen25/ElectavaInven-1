import io
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.audit.models import AuditLog
from apps.components.models import Component

pytestmark = pytest.mark.django_db


def _defs(category):
    return {d.key: d.pk for d in category.specification_definitions.all()} | {
        d.key: d.pk for d in category.parent.specification_definitions.all()
    } if category.parent else {d.key: d.pk for d in category.specification_definitions.all()}


@pytest.fixture
def eng(client_for):
    return client_for("HARDWARE_ENGINEER")


def _create_cap(client, cat, **overrides):
    d = _defs(cat)
    payload = {
        "name": "Capacitor 100nF 50V X7R 0603",
        "category": cat.pk,
        "specifications": [{"definition": d["capacitance"], "value": "100nF"}, {"definition": d["dielectric"], "value": "x7r"}],
        "aliases": [{"alias": "C-100N", "alias_type": "KICAD_VALUE"}],
    }
    payload.update(overrides)
    return client.post("/api/components", payload, format="json")


def test_create_component_auto_pn_specs_and_audit(eng, capacitor_category):
    resp = _create_cap(eng, capacitor_category)
    assert resp.status_code == 201, resp.content
    assert resp.data["internal_part_number"] == "CAP-00001"
    specs = {s["key"]: s for s in resp.data["specifications"]}
    assert specs["capacitance"]["display_value"] == "100 nF"
    assert Decimal(specs["capacitance"]["value"]) == Decimal("1E-7")
    assert specs["dielectric"]["value"] == "X7R"  # normalised to canonical choice
    assert resp.data["aliases"][0]["alias"] == "C-100N"
    log = AuditLog.objects.get(action="CREATE", entity_type="components.component")
    assert log.new_value["specifications"]["capacitance"] == "100 nF"
    second = _create_cap(eng, capacitor_category, name="Another cap")
    assert second.data["internal_part_number"] == "CAP-00002"


def test_inherited_spec_definition_accepted(eng, capacitor_category):
    d = _defs(capacitor_category)
    resp = _create_cap(
        eng, capacitor_category,
        specifications=[{"definition": d["capacitance"], "value": "1u"}, {"definition": d["rohs_note"], "value": "ok"}],
    )
    assert resp.status_code == 201, resp.content


def test_required_spec_enforced(eng, capacitor_category):
    resp = _create_cap(eng, capacitor_category, specifications=[])
    assert resp.status_code == 400
    assert "Capacitance" in str(resp.data["specifications"])


def test_invalid_spec_values_rejected(eng, capacitor_category, ic_category):
    d = _defs(capacitor_category)
    bad_enum = _create_cap(eng, capacitor_category, specifications=[
        {"definition": d["capacitance"], "value": "1u"}, {"definition": d["dielectric"], "value": "Z5U"}])
    assert bad_enum.status_code == 400
    bad_num = _create_cap(eng, capacitor_category, specifications=[{"definition": d["capacitance"], "value": "lots"}])
    assert bad_num.status_code == 400
    foreign = ic_category.specification_definitions.first()
    wrong_cat = _create_cap(eng, capacitor_category, specifications=[
        {"definition": d["capacitance"], "value": "1u"}, {"definition": foreign.pk, "value": True}])
    assert wrong_cat.status_code == 400
    assert Component.objects.count() == 0  # nothing partially written


def test_manual_pn_and_uniqueness(eng, ic_category, ti, soic8):
    payload = {"internal_part_number": "ic-can-00099", "mpn": "TCAN1042HGVDRQ1", "name": "CAN Transceiver",
               "category": ic_category.pk, "manufacturer": ti.pk, "package": soic8.pk}
    first = eng.post("/api/components", payload, format="json")
    assert first.status_code == 201, first.content
    assert first.data["internal_part_number"] == "IC-CAN-00099"
    dup_pn = eng.post("/api/components", {**payload, "mpn": "OTHER"}, format="json")
    assert dup_pn.status_code == 400 and "internal_part_number" in dup_pn.data
    dup_mpn = eng.post("/api/components", {**payload, "internal_part_number": "", "mpn": " tcan1042hgvdrq1 "}, format="json")
    assert dup_mpn.status_code == 400 and "mpn" in dup_mpn.data


def test_mpn_requires_manufacturer(eng, ic_category):
    resp = eng.post("/api/components", {"name": "X", "mpn": "ABC", "category": ic_category.pk}, format="json")
    assert resp.status_code == 400 and "manufacturer" in resp.data


def test_update_component_and_pn_immutable(eng, capacitor_category):
    cid = _create_cap(eng, capacitor_category).data["id"]
    d = _defs(capacitor_category)
    resp = eng.patch(f"/api/components/{cid}", {
        "description": "Updated", "lifecycle_status": "NRND",
        "specifications": [{"definition": d["capacitance"], "value": "220n"}],
    }, format="json")
    assert resp.status_code == 200, resp.content
    assert resp.data["description"] == "Updated"
    assert [s["display_value"] for s in resp.data["specifications"]] == ["220 nF"]  # dielectric removed (replace semantics)
    log = AuditLog.objects.filter(action="UPDATE", entity_type="components.component").latest("id")
    assert log.old_value["specifications"]["capacitance"] == "100 nF"
    assert log.new_value["specifications"] == {"capacitance": "220 nF"}
    assert "search_document" not in log.new_value
    immut = eng.patch(f"/api/components/{cid}", {"internal_part_number": "CAP-99999"}, format="json")
    assert immut.status_code == 400


def test_viewer_cannot_edit_or_delete(client_for, eng, capacitor_category):
    cid = _create_cap(eng, capacitor_category).data["id"]
    viewer = client_for("VIEWER")
    assert viewer.get(f"/api/components/{cid}").status_code == 200
    assert viewer.patch(f"/api/components/{cid}", {"name": "x"}, format="json").status_code == 403
    assert viewer.delete(f"/api/components/{cid}").status_code == 403
    assert eng.delete(f"/api/components/{cid}").status_code == 403  # engineers lack component.delete


def test_soft_delete_hides_but_keeps_record_and_pn(client_for, eng, capacitor_category):
    cid = _create_cap(eng, capacitor_category).data["id"]
    admin = client_for("ADMIN")
    assert admin.delete(f"/api/components/{cid}").status_code == 204
    assert admin.get(f"/api/components/{cid}").status_code == 404
    assert Component.all_objects.filter(pk=cid, deleted_at__isnull=False).exists()
    again = _create_cap(eng, capacitor_category)
    assert again.data["internal_part_number"] == "CAP-00002"  # PN never reused
    assert AuditLog.objects.filter(action="DELETE", entity_id=str(cid)).exists()


@pytest.mark.parametrize("term", ["CAP-00001", "100 nF", "c-100n", "capacitors", "x7r", "0603"])
def test_search_matches_pn_specs_alias_category(eng, capacitor_category, term):
    _create_cap(eng, capacitor_category)
    resp = eng.get("/api/components", {"search": term})
    assert resp.status_code == 200
    assert resp.data["count"] == 1, term


def test_search_mpn_manufacturer_package(eng, ic_category, ti, soic8):
    eng.post("/api/components", {"mpn": "TCAN1042HGVDRQ1", "name": "CAN Transceiver", "category": ic_category.pk,
                                 "manufacturer": ti.pk, "package": soic8.pk}, format="json")
    for term in ["1042", "texas", "soic", "TI can"]:
        assert eng.get("/api/components", {"search": term}).data["count"] == 1, term
    assert eng.get("/api/components", {"search": "stm32"}).data["count"] == 0


def test_filters_and_ordering(eng, capacitor_category, ic_category, ti):
    _create_cap(eng, capacitor_category)
    eng.post("/api/components", {"mpn": "A1", "name": "Zeta", "category": ic_category.pk, "manufacturer": ti.pk,
                                 "lifecycle_status": "OBSOLETE"}, format="json")
    assert eng.get("/api/components", {"category": capacitor_category.parent_id}).data["count"] == 1  # includes children
    assert eng.get("/api/components", {"lifecycle_status": "OBSOLETE"}).data["count"] == 1
    assert eng.get("/api/components", {"manufacturer": ti.pk}).data["count"] == 1
    names = [c["name"] for c in eng.get("/api/components", {"ordering": "-name"}).data["results"]]
    assert names[0] == "Zeta"


def test_manufacturer_rename_refreshes_search(client_for, eng, ic_category, ti):
    eng.post("/api/components", {"mpn": "A1", "name": "Part", "category": ic_category.pk, "manufacturer": ti.pk}, format="json")
    resp = eng.patch(f"/api/manufacturers/{ti.pk}", {"name": "Texas Instruments Inc"}, format="json")
    assert resp.status_code == 200
    assert eng.get("/api/components", {"search": "instruments inc"}).data["count"] == 1


def _png_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buf, format="PNG")
    return buf.getvalue()


def test_image_upload_validation(eng, capacitor_category):
    cid = _create_cap(eng, capacitor_category).data["id"]
    ok = eng.post(f"/api/components/{cid}/image", {"file": SimpleUploadedFile("a.png", _png_bytes(), "image/png")},
                  format="multipart")
    assert ok.status_code == 200, ok.content
    assert ok.data["image_url"].startswith("/media/components/images/")
    assert "a.png" not in ok.data["image_url"]  # client filename never used for storage
    fake = eng.post(f"/api/components/{cid}/image",
                    {"file": SimpleUploadedFile("evil.png", b"<script>alert(1)</script>", "image/png")}, format="multipart")
    assert fake.status_code == 400
    exe = eng.post(f"/api/components/{cid}/image", {"file": SimpleUploadedFile("x.exe", b"MZ..", "application/octet-stream")},
                   format="multipart")
    assert exe.status_code == 400
    assert eng.delete(f"/api/components/{cid}/image").data["image_url"] is None


def test_datasheet_upload_requires_pdf(eng, capacitor_category):
    cid = _create_cap(eng, capacitor_category).data["id"]
    bad = eng.post(f"/api/components/{cid}/datasheet", {"file": SimpleUploadedFile("d.pdf", b"not a pdf", "application/pdf")},
                   format="multipart")
    assert bad.status_code == 400
    good = eng.post(f"/api/components/{cid}/datasheet",
                    {"file": SimpleUploadedFile("d.pdf", b"%PDF-1.7\n%test\n", "application/pdf")}, format="multipart")
    assert good.status_code == 200
    assert good.data["datasheet_file_url"].endswith(".pdf")

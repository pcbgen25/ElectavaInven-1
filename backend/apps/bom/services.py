"""BOM business operations: KiCad import, revision lifecycle, comparison and cost summary."""
import csv
import io
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import record
from apps.components.models import Component

from .models import BOM, BOMItem, BOMRevision

MAX_IMPORT_BYTES = 2 * 1024 * 1024
MAX_IMPORT_ROWS = 5000

# Standard field -> header names recognised automatically (case-insensitive).
STANDARD_FIELDS: Dict[str, List[str]] = {
    "reference": ["reference", "references", "ref", "designator", "designators", "refdes"],
    "value": ["value", "val"],
    "footprint": ["footprint", "package"],
    "quantity": ["quantity", "qty", "qnty", "count"],
    "mpn": ["mpn", "manufacturer part number", "manufacturer_part_number", "mfr part number", "part number"],
    "internal_pn": ["internal pn", "internal_pn", "ipn", "internal part number"],
    "description": ["description", "desc"],
    "manufacturer": ["manufacturer", "mfr", "manufacturer name"],
}


class MatchStatus:
    MATCHED = "MATCHED"
    NEW = "NEW"
    UNMATCHED = "UNMATCHED"
    AMBIGUOUS = "AMBIGUOUS"


class DiffStatus:
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    QUANTITY_CHANGED = "QUANTITY CHANGED"
    REFERENCE_CHANGED = "REFERENCE CHANGED"
    COMPONENT_CHANGED = "COMPONENT CHANGED"
    UNCHANGED = "UNCHANGED"


LOCKED_STATUSES = (BOMRevision.Status.RELEASED, BOMRevision.Status.OBSOLETE)


# ------------------------------------------------------------------------------------- import
def decode_upload(raw: bytes) -> str:
    if not raw:
        raise ValidationError({"file": "The file is empty."})
    if len(raw) > MAX_IMPORT_BYTES:
        raise ValidationError({"file": f"The file is larger than {MAX_IMPORT_BYTES // (1024 * 1024)} MB."})
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationError({"file": "The file is not valid UTF-8 / Windows-1252 text."})


def _reader(file_content: str) -> csv.DictReader:
    try:
        dialect = csv.Sniffer().sniff(file_content[:2048], delimiters=",;\t")
        return csv.DictReader(io.StringIO(file_content), dialect=dialect)
    except csv.Error:
        return csv.DictReader(io.StringIO(file_content))


def detect_columns(file_content: str) -> Tuple[List[str], Dict[str, Optional[str]], List[Dict[str, str]]]:
    """Return (columns, detected mapping standard_field -> column, sample rows)."""
    reader = _reader(file_content)
    columns = [c for c in (reader.fieldnames or []) if c is not None]
    if not columns:
        raise ValidationError({"file": "No header row found. Export the BOM from KiCad as CSV with headers."})
    lowered = {c.strip().lower(): c for c in columns}
    mapping = {field: next((lowered[a] for a in aliases if a in lowered), None) for field, aliases in STANDARD_FIELDS.items()}
    sample = []
    for i, row in enumerate(reader):
        if i >= 5:
            break
        sample.append({c: (row.get(c) or "") for c in columns})
    return columns, mapping, sample


def parse_kicad_csv(file_content: str, mapping: Dict[str, str] = None) -> List[Dict]:
    """Parse KiCad CSV into standardized rows.

    ``mapping`` maps standard field -> CSV column. For backwards compatibility a mapping of
    CSV column -> standard field (the old format) is also accepted.
    """
    columns, detected, _ = detect_columns(file_content)
    if mapping:
        if set(mapping.keys()) <= set(STANDARD_FIELDS):
            field_to_col = {**detected, **{k: v for k, v in mapping.items() if v}}
        else:  # legacy: {"Reference": "reference", ...}
            field_to_col = {**detected, **{std: col for col, std in mapping.items()}}
    else:
        field_to_col = detected
    unknown = [c for c in field_to_col.values() if c and c not in columns]
    if unknown:
        raise ValidationError({"mapping": f"Unknown column(s): {', '.join(unknown)}"})
    if not field_to_col.get("reference") and not field_to_col.get("quantity"):
        raise ValidationError({"mapping": "Map at least the Reference or the Quantity column."})

    items = []
    for line_no, row in enumerate(_reader(file_content), start=2):
        if len(items) >= MAX_IMPORT_ROWS:
            raise ValidationError({"file": f"Too many rows (max {MAX_IMPORT_ROWS})."})
        item = {field: ((row.get(col) or "").strip() if col else "") for field, col in field_to_col.items()}
        if not any(item.values()):
            continue
        refs = [r.strip() for r in item.get("reference", "").replace(";", ",").replace(" ", ",").split(",") if r.strip()]
        raw_qty = item.get("quantity", "")
        try:
            qty = Decimal(raw_qty) if raw_qty else Decimal(len(refs) or 1)
        except InvalidOperation:
            qty = Decimal(len(refs) or 1)
        item["designators"] = refs
        item["quantity"] = qty
        item["line"] = line_no
        items.append(item)
    if not items:
        raise ValidationError({"file": "The file contains no BOM rows."})
    return items


def match_component(item: Dict) -> Tuple[Optional[Component], str]:
    """Match a parsed item to an existing (non-deleted) component: internal PN first, then MPN."""
    for field, lookup in (("internal_pn", "internal_part_number__iexact"), ("mpn", "mpn__iexact")):
        value = item.get(field)
        if value:
            matches = list(Component.objects.filter(**{lookup: value})[:2])
            if len(matches) == 1:
                return matches[0], MatchStatus.MATCHED
            if len(matches) > 1:
                return None, MatchStatus.AMBIGUOUS
    return None, MatchStatus.UNMATCHED


def preview_bom_import(raw_items: List[Dict]) -> List[Dict]:
    annotated = []
    for idx, item in enumerate(raw_items):
        comp, status = match_component(item)
        annotated.append({
            "id": idx,
            "raw": {**item, "quantity": str(item["quantity"])},
            "matched_component_id": comp.id if comp else None,
            "matched_component_pn": comp.internal_part_number if comp else None,
            "matched_component_mpn": comp.mpn if comp else None,
            "match_status": status,
        })
    return annotated


@transaction.atomic
def create_bom_from_import(project, name: str, user, items: List[Dict], description: str = "", request=None) -> BOM:
    """Create a BOM with revision REV A from confirmed import rows.

    ``items``: [{"component": Component, "quantity": Decimal > 0, "designators": [...], "description": str}].
    Unit cost snapshots stay NULL until supplier pricing exists (Phase 4); they are never faked as 0.
    """
    if not items:
        raise ValidationError({"items": "At least one matched row is required."})
    bom = BOM.objects.create(project=project, name=name, description=description, created_by=user)
    rev = BOMRevision.objects.create(bom=bom, revision_number="REV A", created_by=user)
    BOMItem.objects.bulk_create([
        BOMItem(
            revision=rev, component=row["component"], designators=row.get("designators") or [],
            quantity=row["quantity"], description=row.get("description", "")[:500],
        )
        for row in items
    ])
    record(AuditAction.CREATE, entity_type="bom.bom", entity_id=bom.pk, entity_repr=str(bom),
           new_value={"imported_rows": len(items), "revision": rev.revision_number}, user=user, request=request)
    return bom


# ------------------------------------------------------------------------------------- lifecycle
def ensure_revision_editable(revision: BOMRevision) -> None:
    if revision.status in LOCKED_STATUSES:
        raise ValidationError(f"Revision {revision.revision_number} is {revision.status.lower()} and cannot be modified. "
                              "Create a new revision instead.")


@transaction.atomic
def release_revision(revision: BOMRevision, user, request=None) -> BOMRevision:
    revision = BOMRevision.objects.select_for_update().get(pk=revision.pk)
    if revision.status in LOCKED_STATUSES:
        raise ValidationError(f"Revision is already {revision.status.lower()}.")
    if not revision.items.exists():
        raise ValidationError("An empty revision cannot be released.")
    revision.status = BOMRevision.Status.RELEASED
    revision.released_by = user
    revision.released_at = timezone.now()
    revision.save(update_fields=["status", "released_by", "released_at", "updated_at"])
    record(AuditAction.BOM_RELEASE, entity_type="bom.bomrevision", entity_id=revision.pk, entity_repr=str(revision),
           new_value={"status": "RELEASED"}, user=user, request=request)
    return revision


# ------------------------------------------------------------------------------------- compare / cost
def _aggregate(revision: BOMRevision) -> Dict[int, Dict]:
    """Collapse lines by component (the same part may appear on several lines)."""
    out: Dict[int, Dict] = {}
    for item in revision.items.all():
        agg = out.setdefault(item.component_id, {"quantity": Decimal("0"), "designators": []})
        agg["quantity"] += item.quantity
        agg["designators"].extend(item.designators or [])
    return out


def compare_revisions(rev_a: BOMRevision, rev_b: BOMRevision) -> List[Dict]:
    items_a, items_b = _aggregate(rev_a), _aggregate(rev_b)
    components = {
        c.id: c for c in Component.all_objects.filter(id__in=set(items_a) | set(items_b)).only("id", "internal_part_number", "mpn")
    }
    diffs = []
    for comp_id in sorted(set(items_a) | set(items_b), key=lambda c: components[c].internal_part_number if c in components else ""):
        a, b = items_a.get(comp_id), items_b.get(comp_id)
        if a and not b:
            status = DiffStatus.REMOVED
        elif b and not a:
            status = DiffStatus.ADDED
        elif a["quantity"] != b["quantity"]:
            status = DiffStatus.QUANTITY_CHANGED
        elif sorted(a["designators"]) != sorted(b["designators"]):
            status = DiffStatus.REFERENCE_CHANGED
        else:
            status = DiffStatus.UNCHANGED
        comp = components.get(comp_id)
        diffs.append({
            "component_id": comp_id,
            "internal_part_number": comp.internal_part_number if comp else None,
            "mpn": comp.mpn if comp else None,
            "status": status,
            "quantity_a": a["quantity"] if a else Decimal("0"),
            "quantity_b": b["quantity"] if b else Decimal("0"),
            "designators_a": sorted(a["designators"]) if a else [],
            "designators_b": sorted(b["designators"]) if b else [],
        })
    return diffs


def calculate_bom_cost(revision: BOMRevision) -> Dict:
    """Cost summary from snapshots. Lines without a price are counted, never treated as free."""
    total, priced, unpriced = Decimal("0"), 0, 0
    for item in revision.items.all():
        if item.total_cost_snapshot is not None:
            total += item.total_cost_snapshot
            priced += 1
        else:
            unpriced += 1
    return {"total_cost": total, "priced_lines": priced, "unpriced_lines": unpriced, "complete": unpriced == 0}

import csv
import io
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from django.db import transaction
from django.db.models import Q
from apps.components.models import Component
from apps.projects.models import Project
from .models import BOM, BOMRevision, BOMItem

class MatchStatus:
    MATCHED = "MATCHED"
    NEW = "NEW"
    UNMATCHED = "UNMATCHED"
    AMBIGUOUS = "AMBIGUOUS"

class DiffStatus:
    ADDED = "ADDED"
    REMOVED = "REMOVED"
    QUANTITY_CHANGED = "QUANTITY CHANGED"
    COMPONENT_CHANGED = "COMPONENT CHANGED"
    UNCHANGED = "UNCHANGED"

def parse_kicad_csv(file_content: str, mapping: Dict[str, str] = None) -> List[Dict]:
    """Parse KiCad CSV and return standardized item dictionaries."""
    if mapping is None:
        mapping = {
            "Reference": "reference",
            "Value": "value",
            "Footprint": "footprint",
            "Quantity": "quantity",
            "MPN": "mpn",
            "Internal PN": "internal_pn",
            "Manufacturer": "manufacturer"
        }

    # Detect delimiter safely
    try:
        dialect = csv.Sniffer().sniff(file_content[:1024])
        reader = csv.DictReader(io.StringIO(file_content), dialect=dialect)
    except:
        reader = csv.DictReader(io.StringIO(file_content))
    
    items = []
    for row in reader:
        item = {}
        for csv_col, std_field in mapping.items():
            val = row.get(csv_col) or row.get(csv_col.lower()) or row.get(csv_col.upper())
            item[std_field] = val.strip() if val else ""
        
        # Split references (e.g., "R1, R2, R3" -> ["R1", "R2", "R3"])
        refs = [r.strip() for r in item.get("reference", "").replace(" ", ",").split(",") if r.strip()]
        
        # Quantity
        try:
            qty = Decimal(item.get("quantity", len(refs) if refs else 1))
        except:
            qty = Decimal(len(refs) if refs else 1)
            
        item["designators"] = refs
        item["quantity"] = qty
        
        items.append(item)
    return items

def match_component(item: Dict) -> Tuple[Optional[Component], str]:
    """Match a parsed item to an existing component in the DB."""
    internal_pn = item.get("internal_pn")
    mpn = item.get("mpn")
    
    if internal_pn:
        qs = Component.objects.filter(internal_part_number=internal_pn)
        if qs.count() == 1:
            return qs.first(), MatchStatus.MATCHED
        elif qs.count() > 1:
            return None, MatchStatus.AMBIGUOUS
            
    if mpn:
        qs = Component.objects.filter(mpn=mpn)
        if qs.count() == 1:
            return qs.first(), MatchStatus.MATCHED
        elif qs.count() > 1:
            return None, MatchStatus.AMBIGUOUS
            
    # As a fallback, we could check value + footprint, but it's prone to false positives
    return None, MatchStatus.UNMATCHED

def preview_bom_import(raw_items: List[Dict]) -> List[Dict]:
    """Annotate raw items with component matching info for preview."""
    annotated = []
    for idx, item in enumerate(raw_items):
        comp, status = match_component(item)
        
        # Note: If user wants to specify it's a NEW component to be created, they do it later via UI.
        
        annotated.append({
            "id": idx, # UI key
            "raw": item,
            "matched_component_id": comp.id if comp else None,
            "matched_component_pn": comp.internal_part_number if comp else None,
            "match_status": status
        })
    return annotated

@transaction.atomic
def create_bom_from_import(project: Project, name: str, user, matched_items: List[Dict]) -> BOM:
    """Create a new BOM and Revision from a confirmed import."""
    bom = BOM.objects.create(
        project=project,
        name=name,
        created_by=user
    )
    rev = BOMRevision.objects.create(
        bom=bom,
        revision_number="REV A",
        created_by=user
    )
    
    bom_items = []
    for item in matched_items:
        comp_id = item.get("matched_component_id")
        if not comp_id:
            raise ValueError(f"Missing matched_component_id for item: {item.get('raw', {}).get('reference')}")
            
        comp = Component.objects.get(id=comp_id)
        raw = item["raw"]
        
        # Fetch current price here if available
        # In a real system, we'd query supplier APIs or internal price caches.
        # For Phase 2, we simulate it with a dummy 0.00 or the component's placeholder.
        unit_cost = Decimal("0.00") 
        total_cost = unit_cost * raw["quantity"]
        
        bom_items.append(BOMItem(
            revision=rev,
            component=comp,
            designators=raw.get("designators", []),
            quantity=raw["quantity"],
            description=raw.get("value", ""),
            unit_cost_snapshot=unit_cost,
            total_cost_snapshot=total_cost
        ))
        
    BOMItem.objects.bulk_create(bom_items)
    return bom

def compare_revisions(rev_a: BOMRevision, rev_b: BOMRevision) -> List[Dict]:
    """Compare two revisions and return differences."""
    items_a = {i.component_id: i for i in rev_a.items.all()}
    items_b = {i.component_id: i for i in rev_b.items.all()}
    
    all_comps = set(items_a.keys()).union(set(items_b.keys()))
    
    diffs = []
    for comp_id in all_comps:
        a = items_a.get(comp_id)
        b = items_b.get(comp_id)
        
        if a and not b:
            diffs.append({
                "component_id": comp_id,
                "status": DiffStatus.REMOVED,
                "quantity_a": a.quantity,
                "quantity_b": 0,
                "designators_a": a.designators,
                "designators_b": []
            })
        elif b and not a:
            diffs.append({
                "component_id": comp_id,
                "status": DiffStatus.ADDED,
                "quantity_a": 0,
                "quantity_b": b.quantity,
                "designators_a": [],
                "designators_b": b.designators
            })
        else:
            if a.quantity != b.quantity:
                diffs.append({
                    "component_id": comp_id,
                    "status": DiffStatus.QUANTITY_CHANGED,
                    "quantity_a": a.quantity,
                    "quantity_b": b.quantity,
                    "designators_a": a.designators,
                    "designators_b": b.designators
                })
            elif set(a.designators) != set(b.designators):
                # Technically same component/qty, different designators.
                diffs.append({
                    "component_id": comp_id,
                    "status": "REFERENCE CHANGED",
                    "quantity_a": a.quantity,
                    "quantity_b": b.quantity,
                    "designators_a": a.designators,
                    "designators_b": b.designators
                })
            else:
                diffs.append({
                    "component_id": comp_id,
                    "status": DiffStatus.UNCHANGED,
                    "quantity_a": a.quantity,
                    "quantity_b": b.quantity,
                    "designators_a": a.designators,
                    "designators_b": b.designators
                })
                
    return diffs

def calculate_bom_cost(revision: BOMRevision) -> Decimal:
    """Calculate the total cost of a BOM revision."""
    total = Decimal("0.00")
    for item in revision.items.all():
        if item.total_cost_snapshot:
            total += item.total_cost_snapshot
    return total

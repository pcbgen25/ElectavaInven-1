"""Component business operations. Views must call these instead of writing models directly."""
from __future__ import annotations

import os
import uuid
from decimal import Decimal
from typing import Any, Iterable

from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from apps.audit import services as audit
from apps.audit.models import AuditAction
from apps.core.exceptions import Conflict
from apps.core.files import IMAGE, PDF, validate_upload

from .models import (
    Category,
    Component,
    ComponentAlias,
    ComponentSpecification,
    PartNumberSequence,
    SpecificationDefinition,
)
from .units import UnitParseError, format_engineering, parse_engineering

DT = SpecificationDefinition.DataType


# --- normalisation ----------------------------------------------------------
def normalize_identifier(value: str | None) -> str:
    """Upper-case and strip all whitespace. Used for MPN/alias matching."""
    return "".join((value or "").split()).upper()


# --- part numbers -----------------------------------------------------------
def generate_internal_part_number(category: Category) -> str:
    """Next free ``<PREFIX>-NNNNN``. Concurrency-safe via row lock on the sequence."""
    prefix = category.code
    try:
        with transaction.atomic():
            PartNumberSequence.objects.get_or_create(prefix=prefix)
    except IntegrityError:
        pass  # created concurrently
    with transaction.atomic():
        seq = PartNumberSequence.objects.select_for_update().get(prefix=prefix)
        while True:
            seq.last_value += 1
            pn = f"{prefix}-{seq.last_value:05d}"
            if not Component.all_objects.filter(internal_part_number=pn).exists():
                break
        seq.save(update_fields=["last_value"])
    return pn


# --- specifications ---------------------------------------------------------
def effective_definitions(category: Category, include_inactive: bool = False) -> list[SpecificationDefinition]:
    """Definitions of the category and all its ancestors (ancestors first)."""
    chain = category.ancestors() + [category]
    qs = SpecificationDefinition.objects.filter(category__in=chain).select_related("category")
    if not include_inactive:
        qs = qs.filter(is_active=True)
    order = {c.pk: i for i, c in enumerate(chain)}
    return sorted(qs, key=lambda d: (order[d.category_id], d.sort_order, d.name))


def parse_spec_value(definition: SpecificationDefinition, raw: Any) -> dict[str, Any]:
    """Return typed column values for a raw input, or raise ValidationError."""
    values: dict[str, Any] = {"value_string": "", "value_integer": None, "value_decimal": None, "value_boolean": None}
    dt = definition.data_type
    try:
        if dt == DT.STRING:
            text = str(raw).strip()
            if len(text) > 255:
                raise ValueError("Text must be 255 characters or fewer.")
            values["value_string"] = text
        elif dt == DT.ENUM:
            text = str(raw).strip()
            choices = [str(c) for c in (definition.enum_choices or [])]
            match = next((c for c in choices if c.lower() == text.lower()), None)
            if match is None:
                raise ValueError(f"Must be one of: {', '.join(choices)}.")
            values["value_string"] = match
        elif dt == DT.INTEGER:
            if isinstance(raw, bool):
                raise ValueError("Must be a whole number.")
            number = parse_engineering(raw, definition.unit, definition.use_si_prefix)
            if number != number.to_integral_value():
                raise ValueError("Must be a whole number.")
            values["value_integer"] = int(number)
        elif dt == DT.DECIMAL:
            number = parse_engineering(raw, definition.unit, definition.use_si_prefix)
            if abs(number) >= Decimal("1e16") or (number != 0 and abs(number) < Decimal("1e-18")):
                raise ValueError("Value is out of the supported range.")
            values["value_decimal"] = number
        elif dt == DT.BOOLEAN:
            if isinstance(raw, bool):
                values["value_boolean"] = raw
            elif str(raw).strip().lower() in {"true", "yes", "1", "y"}:
                values["value_boolean"] = True
            elif str(raw).strip().lower() in {"false", "no", "0", "n"}:
                values["value_boolean"] = False
            else:
                raise ValueError("Must be yes or no.")
    except (UnitParseError, ValueError) as exc:
        raise ValidationError({"specifications": [f"{definition.name}: {exc}"]}) from exc
    return values


def display_spec_value(spec: ComponentSpecification) -> str:
    d = spec.definition
    if d.data_type in (DT.STRING, DT.ENUM):
        return f"{spec.value_string} {d.unit}".strip() if d.unit and d.data_type == DT.STRING else spec.value_string
    if d.data_type == DT.BOOLEAN:
        return "" if spec.value_boolean is None else ("Yes" if spec.value_boolean else "No")
    if d.data_type == DT.INTEGER:
        return "" if spec.value_integer is None else f"{spec.value_integer} {d.unit}".strip()
    return format_engineering(spec.value_decimal, d.unit, d.use_si_prefix)


def _is_blank(raw: Any) -> bool:
    return raw is None or (isinstance(raw, str) and raw.strip() == "")


def set_specifications(component: Component, items: Iterable[dict]) -> None:
    """Replace the component's specification set. ``items``: [{definition: id, value: raw}]."""
    allowed = {d.pk: d for d in effective_definitions(component.category, include_inactive=True)}
    provided: dict[int, Any] = {}
    errors: list[str] = []
    for item in items:
        def_id = item.get("definition")
        if def_id not in allowed:
            errors.append(f"Specification #{def_id} does not belong to category '{component.category}'.")
            continue
        if def_id in provided:
            errors.append(f"{allowed[def_id].name}: provided more than once.")
            continue
        provided[def_id] = item.get("value")
    for d in allowed.values():
        if d.is_required and d.is_active and _is_blank(provided.get(d.pk)):
            errors.append(f"{d.name}: this specification is required.")
    if errors:
        raise ValidationError({"specifications": errors})

    existing = {s.definition_id: s for s in component.specifications.all()}
    keep: set[int] = set()
    for def_id, raw in provided.items():
        if _is_blank(raw):
            continue
        values = parse_spec_value(allowed[def_id], raw)
        spec = existing.get(def_id) or ComponentSpecification(component=component, definition=allowed[def_id])
        for k, v in values.items():
            setattr(spec, k, v)
        spec.save()
        keep.add(def_id)
    component.specifications.exclude(definition_id__in=keep).delete()


def drop_incompatible_specifications(component: Component) -> None:
    allowed = [d.pk for d in effective_definitions(component.category, include_inactive=True)]
    component.specifications.exclude(definition_id__in=allowed).delete()


def specs_snapshot(component: Component) -> dict[str, str]:
    return {
        s.definition.key: display_spec_value(s)
        for s in component.specifications.select_related("definition").all()
    }


# --- aliases ----------------------------------------------------------------
def set_aliases(component: Component, items: Iterable[dict]) -> None:
    seen: set[str] = set()
    rows = []
    for item in items:
        alias = " ".join(str(item.get("alias", "")).split())
        norm = normalize_identifier(alias)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        rows.append((alias, norm, item.get("alias_type") or ComponentAlias.AliasType.OTHER, item.get("notes", "")))
    component.aliases.exclude(alias_normalized__in=seen).delete()
    existing = {a.alias_normalized: a for a in component.aliases.all()}
    for alias, norm, alias_type, notes in rows:
        obj = existing.get(norm) or ComponentAlias(component=component, alias_normalized=norm)
        obj.alias, obj.alias_type, obj.notes = alias, alias_type, notes or ""
        obj.save()


def aliases_snapshot(component: Component) -> list[str]:
    return sorted(component.aliases.values_list("alias", flat=True))


# --- search -----------------------------------------------------------------
def rebuild_search_document(component: Component) -> None:
    parts: list[str] = [component.internal_part_number, component.mpn, component.name, component.description]
    if component.manufacturer_id:
        m = component.manufacturer
        parts += [m.name, m.short_name]
    cat = component.category
    parts += [cat.full_path, cat.code]
    if component.package_id:
        parts.append(component.package.name)
    parts += list(component.aliases.values_list("alias", flat=True))
    for spec in component.specifications.select_related("definition"):
        parts += [spec.definition.name, display_spec_value(spec), spec.value_string]
    doc = " | ".join(p for p in parts if p)
    Component.all_objects.filter(pk=component.pk).update(search_document=doc)
    component.search_document = doc


def rebuild_search_documents_for(*, manufacturer=None, category: Category | None = None, package=None) -> int:
    qs = Component.objects.select_related("manufacturer", "category", "package")
    if manufacturer is not None:
        qs = qs.filter(manufacturer=manufacturer)
    if category is not None:
        qs = qs.filter(category_id__in=category.descendant_ids())
    if package is not None:
        qs = qs.filter(package=package)
    count = 0
    for component in qs.iterator(chunk_size=500):
        rebuild_search_document(component)
        count += 1
    return count


# --- component lifecycle ----------------------------------------------------
def _full_snapshot(component: Component) -> dict:
    return audit.snapshot(
        component, {"specifications": specs_snapshot(component), "aliases": aliases_snapshot(component)}
    )


def _apply_identity(component: Component) -> None:
    component.internal_part_number = component.internal_part_number.strip().upper()
    component.mpn = component.mpn.strip()
    component.mpn_normalized = normalize_identifier(component.mpn)


def _check_mpn_unique(component: Component) -> None:
    if not component.mpn_normalized:
        return
    qs = Component.objects.filter(manufacturer_id=component.manufacturer_id, mpn_normalized=component.mpn_normalized)
    if component.pk:
        qs = qs.exclude(pk=component.pk)
    clash = qs.first()
    if clash:
        raise ValidationError({"mpn": [f"This manufacturer + MPN already exists as {clash.internal_part_number}."]})


@transaction.atomic
def create_component(*, data: dict, specifications: list | None, aliases: list | None, user, request=None) -> Component:
    component = Component(**data)
    if not component.internal_part_number:
        component.internal_part_number = generate_internal_part_number(component.category)
    _apply_identity(component)
    if Component.all_objects.filter(internal_part_number=component.internal_part_number).exists():
        raise ValidationError({"internal_part_number": ["This internal part number is already used (PNs are never reused)."]})
    _check_mpn_unique(component)
    component.created_by = component.updated_by = user
    component.save()
    set_specifications(component, specifications or [])
    set_aliases(component, aliases or [])
    rebuild_search_document(component)
    audit.record_create(
        component, request=request, user=user,
        extra={"specifications": specs_snapshot(component), "aliases": aliases_snapshot(component)},
    )
    return component


@transaction.atomic
def update_component(
    component: Component, *, data: dict, specifications: list | None, aliases: list | None, user, request=None
) -> Component:
    component = Component.objects.select_for_update().get(pk=component.pk)
    old = _full_snapshot(component)
    if "internal_part_number" in data and data["internal_part_number"].strip().upper() != component.internal_part_number:
        raise ValidationError({"internal_part_number": ["Internal part numbers cannot be changed once assigned."]})
    category_changed = "category" in data and data["category"].pk != component.category_id
    for key, value in data.items():
        setattr(component, key, value)
    _apply_identity(component)
    _check_mpn_unique(component)
    component.updated_by = user
    component.save()
    if specifications is not None:
        set_specifications(component, specifications)
    elif category_changed:
        drop_incompatible_specifications(component)
    if aliases is not None:
        set_aliases(component, aliases)
    rebuild_search_document(component)
    new_extra = {"specifications": specs_snapshot(component), "aliases": aliases_snapshot(component)}
    audit.record_update(component, old, request=request, user=user, extra=new_extra)
    return component


def check_component_deletable(component: Component) -> None:
    """Extension point: later phases (BOM, inventory) add reference checks here."""
    return None


@transaction.atomic
def delete_component(component: Component, *, user, request=None) -> None:
    check_component_deletable(component)
    component.soft_delete(user)
    audit.record_delete(component, request=request, user=user, soft=True)


# --- files ------------------------------------------------------------------
FILE_FIELDS = {"image": IMAGE, "datasheet_file": PDF}


@transaction.atomic
def attach_file(component: Component, field: str, upload, *, user, request=None) -> Component:
    kind = FILE_FIELDS[field]
    validate_upload(upload, kind)
    file_field = getattr(component, field)
    old_name = file_field.name
    ext = os.path.splitext(upload.name)[1].lower()
    file_field.save(f"{uuid.uuid4().hex}{ext}", upload, save=False)
    component.updated_by = user
    component.save(update_fields=[field, "updated_by", "updated_at"])
    if old_name:
        transaction.on_commit(lambda: file_field.storage.delete(old_name))
    audit.record(
        AuditAction.FILE_UPLOAD, entity_type=audit.entity_type_of(component), entity_id=component.pk,
        entity_repr=str(component), old_value={field: old_name or None}, new_value={field: file_field.name},
        metadata={"original_filename": upload.name[:200], "size": upload.size}, request=request, user=user,
    )
    return component


@transaction.atomic
def remove_file(component: Component, field: str, *, user, request=None) -> Component:
    if field not in FILE_FIELDS:
        raise Conflict("Unknown file field.")
    file_field = getattr(component, field)
    old_name = file_field.name
    if not old_name:
        return component
    setattr(component, field, "")
    component.updated_by = user
    component.save(update_fields=[field, "updated_by", "updated_at"])
    storage = file_field.storage
    transaction.on_commit(lambda: storage.delete(old_name))
    audit.record(
        AuditAction.FILE_DELETE, entity_type=audit.entity_type_of(component), entity_id=component.pk,
        entity_repr=str(component), old_value={field: old_name}, request=request, user=user,
    )
    return component

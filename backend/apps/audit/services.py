"""Audit service. Call ``record()`` explicitly from business services/views."""
from __future__ import annotations

import datetime
import decimal
import uuid
from typing import Any

from django.db import models
from django.db.models.fields.files import FieldFile

from .models import AuditAction, AuditLog

SENSITIVE_KEYS = ("password", "secret", "token", "api_key", "apikey", "authorization", "session")
REDACTED = "***redacted***"
EXCLUDED_FIELDS = {"search_document", "last_login"}


def _is_sensitive(key: str) -> bool:
    k = key.lower()
    return any(s in k for s in SENSITIVE_KEYS)


def _json_safe(value: Any) -> Any:
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, FieldFile):
        return value.name or None
    if isinstance(value, models.Model):
        return value.pk
    if isinstance(value, dict):
        return redact(value)
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    return value


def redact(data: dict | None) -> dict | None:
    if data is None:
        return None
    return {k: (REDACTED if _is_sensitive(str(k)) else _json_safe(v)) for k, v in data.items()}


def snapshot(instance: models.Model, extra: dict | None = None) -> dict:
    """JSON-safe dict of concrete field values (FKs as ids). Secrets redacted."""
    data: dict[str, Any] = {}
    for field in instance._meta.concrete_fields:
        if field.name in EXCLUDED_FIELDS:
            continue
        key = field.attname if isinstance(field, models.ForeignKey) else field.name
        data[key] = getattr(instance, field.attname)
    if extra:
        data.update(extra)
    return redact(data) or {}


def diff(old: dict, new: dict) -> tuple[dict, dict]:
    keys = set(old) | set(new)
    changed = {k for k in keys if old.get(k) != new.get(k)}
    return {k: old.get(k) for k in changed}, {k: new.get(k) for k in changed}


def _client_ip(request) -> str | None:
    if request is None:
        return None
    # Only trust X-Forwarded-For if a reverse proxy sets it (production config).
    ip = request.META.get("REMOTE_ADDR")
    return ip or None


def record(
    action: str,
    *,
    entity_type: str,
    entity_id: Any = "",
    entity_repr: str = "",
    old_value: dict | None = None,
    new_value: dict | None = None,
    metadata: dict | None = None,
    user=None,
    request=None,
) -> AuditLog:
    if user is None and request is not None:
        user = getattr(request, "user", None)
    if user is not None and not getattr(user, "is_authenticated", False):
        user = None
    return AuditLog.objects.create(
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id not in (None, "") else "",
        entity_repr=(entity_repr or "")[:255],
        old_value=redact(old_value),
        new_value=redact(new_value),
        metadata=redact(metadata) or {},
        user=user,
        user_email=getattr(user, "email", "") if user else "",
        ip_address=_client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "")[:255] if request is not None else ""),
    )


def entity_type_of(instance: models.Model) -> str:
    return instance._meta.label_lower


def record_create(instance, *, request=None, user=None, extra: dict | None = None) -> AuditLog:
    return record(
        AuditAction.CREATE,
        entity_type=entity_type_of(instance),
        entity_id=instance.pk,
        entity_repr=str(instance),
        new_value=snapshot(instance, extra),
        request=request,
        user=user,
    )


def record_update(instance, old: dict, *, request=None, user=None, extra: dict | None = None) -> AuditLog | None:
    new = snapshot(instance, extra)
    old_changed, new_changed = diff(old, new)
    old_changed.pop("updated_at", None)
    new_changed.pop("updated_at", None)
    if not new_changed and not old_changed:
        return None
    return record(
        AuditAction.UPDATE,
        entity_type=entity_type_of(instance),
        entity_id=instance.pk,
        entity_repr=str(instance),
        old_value=old_changed,
        new_value=new_changed,
        request=request,
        user=user,
    )


def record_delete(instance, *, request=None, user=None, soft: bool = True) -> AuditLog:
    return record(
        AuditAction.DELETE,
        entity_type=entity_type_of(instance),
        entity_id=instance.pk,
        entity_repr=str(instance),
        old_value=snapshot(instance),
        metadata={"soft_delete": soft},
        request=request,
        user=user,
    )

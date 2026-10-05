"""Account / RBAC business operations."""
from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit import services as audit
from apps.audit.models import AuditAction

from .models import Permission, Role, User
from .rbac_catalog import ALL, PERMISSIONS, ROLES, SUPER_ADMIN


@transaction.atomic
def sync_rbac_catalog(reset_defaults: bool = False) -> None:
    """Idempotently ensure catalog permissions and system roles exist.

    - New system roles receive their default grants.
    - Existing roles keep whatever grants admins configured, unless ``reset_defaults``.
    - SUPER_ADMIN always holds every permission.
    """
    for code, name, module in PERMISSIONS:
        Permission.objects.update_or_create(code=code, defaults={"name": name, "module": module})
    all_perms = list(Permission.objects.all())
    by_code = {p.code: p for p in all_perms}
    for code, spec in ROLES.items():
        role, created = Role.objects.get_or_create(
            code=code, defaults={"name": spec["name"], "description": spec["description"], "is_system": True}
        )
        if not role.is_system:
            role.is_system = True
            role.save(update_fields=["is_system"])
        if spec["permissions"] == ALL:
            role.permissions.set(all_perms)
        elif created or reset_defaults:
            role.permissions.set([by_code[c] for c in spec["permissions"]])


def _guard_super_admin_grant(actor: User, roles: list[Role]) -> None:
    if any(r.code == SUPER_ADMIN for r in roles) and not actor.is_super_admin:
        raise PermissionDenied("Only a Super Admin can grant the Super Admin role.")


def _role_codes(user: User) -> list[str]:
    return sorted(user.roles.values_list("code", flat=True))


@transaction.atomic
def create_user(*, actor: User, request, data: dict, roles: list[Role], password: str | None) -> User:
    _guard_super_admin_grant(actor, roles)
    user = User(**data)
    if password:
        validate_password(password, user)
    user.set_password(password)
    user.save()
    user.roles.set(roles)
    audit.record_create(user, request=request, extra={"roles": _role_codes(user)})
    return user


@transaction.atomic
def update_user(*, actor: User, request, user: User, data: dict, roles: list[Role] | None) -> User:
    if user.is_super_admin and not actor.is_super_admin:
        raise PermissionDenied("Only a Super Admin can modify a Super Admin account.")
    if user.pk == actor.pk and data.get("is_active") is False:
        raise ValidationError({"is_active": ["You cannot deactivate your own account."]})
    old = audit.snapshot(user, {"roles": _role_codes(user)})
    old_roles = set(old["roles"])
    for key, value in data.items():
        setattr(user, key, value)
    user.save()
    if roles is not None:
        _guard_super_admin_grant(actor, roles)
        if user.pk == actor.pk and SUPER_ADMIN in old_roles and SUPER_ADMIN not in {r.code for r in roles}:
            raise ValidationError({"role_codes": ["You cannot remove your own Super Admin role."]})
        user.roles.set(roles)
    user.clear_rbac_cache()
    new_roles = set(_role_codes(user))
    audit.record_update(user, old, request=request, extra={"roles": sorted(new_roles)})
    if new_roles != old_roles:
        audit.record(
            AuditAction.PERMISSION_CHANGE,
            entity_type=audit.entity_type_of(user),
            entity_id=user.pk,
            entity_repr=str(user),
            old_value={"roles": sorted(old_roles)},
            new_value={"roles": sorted(new_roles)},
            request=request,
        )
    return user


@transaction.atomic
def set_password(*, actor: User, request, user: User, password: str) -> None:
    if user.is_super_admin and not actor.is_super_admin:
        raise PermissionDenied("Only a Super Admin can reset a Super Admin password.")
    validate_password(password, user)
    user.set_password(password)
    user.save(update_fields=["password"])
    audit.record(
        AuditAction.PASSWORD_CHANGE,
        entity_type=audit.entity_type_of(user),
        entity_id=user.pk,
        entity_repr=str(user),
        metadata={"reset_by_admin": actor.pk != user.pk},
        request=request,
    )


@transaction.atomic
def set_role_permissions(*, actor: User, request, role: Role, codes: list[str]) -> Role:
    if role.code == SUPER_ADMIN:
        raise ValidationError({"permission_codes": ["Super Admin always has every permission."]})
    perms = list(Permission.objects.filter(code__in=codes))
    unknown = set(codes) - {p.code for p in perms}
    if unknown:
        raise ValidationError({"permission_codes": [f"Unknown permission(s): {', '.join(sorted(unknown))}"]})
    old = sorted(role.permissions.values_list("code", flat=True))
    role.permissions.set(perms)
    new = sorted(p.code for p in perms)
    if old != new:
        audit.record(
            AuditAction.PERMISSION_CHANGE,
            entity_type=audit.entity_type_of(role),
            entity_id=role.pk,
            entity_repr=str(role),
            old_value={"permissions": old},
            new_value={"permissions": new},
            request=request,
        )
    return role

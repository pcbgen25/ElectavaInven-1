"""RBAC permission class enforced on every API view.

Views declare::

    required_permissions = {
        "list": "component.view",
        "create": "component.create",
        "destroy": ["component.delete", "masterdata.manage"],  # any of
        "*": "component.view",                                  # fallback
    }

Special values:
    AUTHENTICATED – any logged-in active user
Anything not declared is DENIED (secure by default).
"""
from rest_framework.permissions import BasePermission

AUTHENTICATED = "__authenticated__"


def _resolve_required(view, request):
    mapping = getattr(view, "required_permissions", None)
    if mapping is None:
        return None
    if isinstance(mapping, (str, list)):
        return mapping
    action = getattr(view, "action", None) or request.method.lower()
    if action in mapping:
        return mapping[action]
    return mapping.get("*")


class HasRBACPermission(BasePermission):
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return False
        if not hasattr(view, request.method.lower()):
            return True  # no handler: DRF responds 405 Method Not Allowed; nothing is executed
        required = _resolve_required(view, request)
        if required is None:
            return False
        if required == AUTHENTICATED:
            return True
        codes = [required] if isinstance(required, str) else list(required)
        return any(user.has_rbac_permission(code) for code in codes)

"""Record authentication events in the audit log. Passwords are never recorded."""
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver

from apps.audit import services as audit
from apps.audit.models import AuditAction


@receiver(user_logged_in, dispatch_uid="audit_login")
def on_login(sender, request, user, **kwargs):
    audit.record(
        AuditAction.LOGIN, entity_type="accounts.user", entity_id=user.pk, entity_repr=str(user),
        user=user, request=request,
    )


@receiver(user_logged_out, dispatch_uid="audit_logout")
def on_logout(sender, request, user, **kwargs):
    if user is None:
        return
    audit.record(
        AuditAction.LOGOUT, entity_type="accounts.user", entity_id=user.pk, entity_repr=str(user),
        user=user, request=request,
    )


@receiver(user_login_failed, dispatch_uid="audit_login_failed")
def on_login_failed(sender, credentials, request=None, **kwargs):
    email = str(credentials.get("email") or credentials.get("username") or "")[:254]
    audit.record(
        AuditAction.LOGIN_FAILED, entity_type="accounts.user", entity_repr=email,
        metadata={"email": email}, request=request,
    )

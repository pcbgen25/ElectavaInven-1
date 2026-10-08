"""Dashboard metrics. Metrics for modules not built yet are returned as
``{"value": null, "available": false, "phase": N}`` so the UI can say so honestly."""
from django.db.models import Count, Q

from apps.audit.models import AuditAction, AuditLog
from apps.components.models import Category, Component
from apps.manufacturers.models import Manufacturer

PENDING_METRICS = {
    # Valuation needs purchase costing, which arrives with purchasing.
    "inventory_value": 4,
    "pending_purchase_requests": 4,
    "pending_purchase_orders": 4,
}

COMPONENT_ENTITY_TYPES = [
    "components.component", "components.category", "components.package",
    "components.specificationdefinition", "manufacturers.manufacturer",
]


def _metric(value, phase: int = 1):
    return {"value": value, "available": True, "phase": phase}


def dashboard_summary(user) -> dict:
    data: dict = {"metrics": {}, "recent_components": [], "recent_activity": []}
    if user.has_rbac_permission("component.view"):
        counts = Component.objects.aggregate(
            total=Count("id"),
            active=Count("id", filter=Q(status=Component.Status.ACTIVE)),
            obsolete=Count("id", filter=Q(lifecycle_status=Component.Lifecycle.OBSOLETE)),
            nrnd=Count("id", filter=Q(lifecycle_status__in=[Component.Lifecycle.NRND, Component.Lifecycle.LAST_TIME_BUY])),
        )
        data["metrics"].update(
            total_components=_metric(counts["total"]),
            active_components=_metric(counts["active"]),
            obsolete_components=_metric(counts["obsolete"]),
            nrnd_components=_metric(counts["nrnd"]),
            categories=_metric(Category.objects.count()),
            manufacturers=_metric(Manufacturer.objects.count()),
        )
        recent = Component.objects.select_related("manufacturer", "category").order_by("-updated_at")[:8]
        data["recent_components"] = [
            {
                "id": c.id,
                "internal_part_number": c.internal_part_number,
                "mpn": c.mpn,
                "name": c.name,
                "manufacturer": c.manufacturer.name if c.manufacturer else None,
                "category": c.category.name,
                "lifecycle_status": c.lifecycle_status,
                "updated_at": c.updated_at,
            }
            for c in recent
        ]
        activity = AuditLog.objects.all()
        if not user.has_rbac_permission("audit.view"):
            activity = activity.filter(
                entity_type__in=COMPONENT_ENTITY_TYPES,
                action__in=[AuditAction.CREATE, AuditAction.UPDATE, AuditAction.DELETE, AuditAction.FILE_UPLOAD],
            )
        data["recent_activity"] = [
            {
                "id": a.id,
                "timestamp": a.timestamp,
                "user_email": a.user_email,
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "entity_repr": a.entity_repr,
            }
            for a in activity[:10]
        ]
    if user.has_rbac_permission("project.view"):
        from apps.projects.models import Project

        data["metrics"]["projects"] = _metric(
            Project.objects.exclude(status__in=[Project.Status.COMPLETED, Project.Status.CANCELLED]).count(), phase=2
        )
    if user.has_rbac_permission("bom.view"):
        from apps.bom.models import BOM

        data["metrics"]["active_boms"] = _metric(BOM.objects.exclude(status=BOM.Status.OBSOLETE).count(), phase=2)
    if user.has_rbac_permission("inventory.view"):
        from apps.inventory.services import stock_summary

        summary = stock_summary()
        data["metrics"]["low_stock"] = _metric(summary["low_stock"], phase=3)
        data["metrics"]["out_of_stock"] = _metric(summary["out_of_stock"], phase=3)
    for key, phase in PENDING_METRICS.items():
        data["metrics"][key] = {"value": None, "available": False, "phase": phase}
    return data

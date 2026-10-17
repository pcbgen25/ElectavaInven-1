import django_filters

from .models import GoodsReceipt, PurchaseOrder, PurchaseRequest


class PurchaseRequestFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status")
    priority = django_filters.CharFilter(field_name="priority")
    project = django_filters.NumberFilter(field_name="project_id")
    bom_revision = django_filters.NumberFilter(field_name="bom_revision_id")

    class Meta:
        model = PurchaseRequest
        fields = ["status", "priority", "project", "bom_revision"]


class PurchaseOrderFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status")
    supplier = django_filters.NumberFilter(field_name="supplier_id")
    project = django_filters.NumberFilter(field_name="project_id")
    purchase_request = django_filters.NumberFilter(field_name="purchase_request_id")

    class Meta:
        model = PurchaseOrder
        fields = ["status", "supplier", "project", "purchase_request", "currency"]


class GoodsReceiptFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status")
    purchase_order = django_filters.NumberFilter(field_name="purchase_order_id")
    warehouse = django_filters.NumberFilter(field_name="warehouse_id")
    supplier = django_filters.NumberFilter(field_name="purchase_order__supplier_id")

    class Meta:
        model = GoodsReceipt
        fields = ["status", "purchase_order", "warehouse", "supplier"]

import django_filters
from django.db.models import Q

from .models import InventoryItem, StockReservation, StockStatus, StockTransaction, WarehouseLocation


class InventoryItemFilter(django_filters.FilterSet):
    component = django_filters.NumberFilter(field_name="component_id")
    warehouse = django_filters.NumberFilter(field_name="warehouse_id")
    location = django_filters.NumberFilter(field_name="location_id")
    status = django_filters.MultipleChoiceFilter(field_name="stock_status", choices=StockStatus.choices)
    has_stock = django_filters.BooleanFilter(method="filter_has_stock")

    class Meta:
        model = InventoryItem
        fields = ["component", "warehouse", "location", "lot_batch"]

    def filter_has_stock(self, queryset, name, value):
        return queryset.filter(quantity_on_hand__gt=0) if value else queryset.filter(quantity_on_hand=0)


class StockTransactionFilter(django_filters.FilterSet):
    component = django_filters.NumberFilter(field_name="component_id")
    warehouse = django_filters.NumberFilter(field_name="warehouse_id")
    location = django_filters.NumberFilter(field_name="location_id")
    performed_by = django_filters.NumberFilter(field_name="performed_by_id")
    transaction_type = django_filters.MultipleChoiceFilter(choices=StockTransaction.TransactionType.choices)
    source_type = django_filters.MultipleChoiceFilter(choices=StockTransaction.SourceType.choices)
    transfer_group_id = django_filters.UUIDFilter()
    date_from = django_filters.IsoDateTimeFilter(field_name="timestamp", lookup_expr="gte")
    date_to = django_filters.IsoDateTimeFilter(field_name="timestamp", lookup_expr="lte")

    class Meta:
        model = StockTransaction
        fields = ["component", "warehouse", "location", "transaction_type", "source_type", "source_id"]


class StockReservationFilter(django_filters.FilterSet):
    component = django_filters.NumberFilter(field_name="component_id")
    warehouse = django_filters.NumberFilter(field_name="warehouse_id")
    project = django_filters.NumberFilter(field_name="project_id")
    bom_revision = django_filters.NumberFilter(field_name="bom_revision_id")
    status = django_filters.MultipleChoiceFilter(choices=StockReservation.Status.choices)

    class Meta:
        model = StockReservation
        fields = ["component", "warehouse", "project", "bom_revision", "status"]


class WarehouseLocationFilter(django_filters.FilterSet):
    warehouse = django_filters.NumberFilter(field_name="warehouse_id")
    is_active = django_filters.BooleanFilter()
    q = django_filters.CharFilter(method="filter_q")

    class Meta:
        model = WarehouseLocation
        fields = ["warehouse", "is_active"]

    def filter_q(self, queryset, name, value):
        return queryset.filter(Q(code__icontains=value) | Q(name__icontains=value))

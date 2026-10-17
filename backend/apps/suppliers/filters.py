import django_filters

from .models import Supplier, SupplierPart


class SupplierFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="status")
    is_active = django_filters.BooleanFilter(field_name="is_active")
    country = django_filters.CharFilter(field_name="country", lookup_expr="iexact")

    class Meta:
        model = Supplier
        fields = ["status", "is_active", "country", "currency"]


class SupplierPartFilter(django_filters.FilterSet):
    supplier = django_filters.NumberFilter(field_name="supplier_id")
    component = django_filters.NumberFilter(field_name="component_id")
    is_preferred = django_filters.BooleanFilter(field_name="is_preferred")
    is_active = django_filters.BooleanFilter(field_name="is_active")

    class Meta:
        model = SupplierPart
        fields = ["supplier", "component", "is_preferred", "is_active", "currency"]

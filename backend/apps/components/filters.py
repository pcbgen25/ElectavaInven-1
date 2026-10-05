import django_filters
from django.db.models import Q

from .models import Category, Component


class ComponentFilter(django_filters.FilterSet):
    category = django_filters.NumberFilter(method="filter_category", help_text="Category id (includes sub-categories)")
    manufacturer = django_filters.NumberFilter(field_name="manufacturer_id")
    package = django_filters.NumberFilter(field_name="package_id")
    status = django_filters.MultipleChoiceFilter(choices=Component.Status.choices)
    lifecycle_status = django_filters.MultipleChoiceFilter(choices=Component.Lifecycle.choices)
    is_rohs = django_filters.BooleanFilter()
    is_reach = django_filters.BooleanFilter()
    has_datasheet = django_filters.BooleanFilter(method="filter_has_datasheet")

    class Meta:
        model = Component
        fields = ["category", "manufacturer", "package", "status", "lifecycle_status", "is_rohs", "is_reach"]

    def filter_category(self, queryset, name, value):
        try:
            category = Category.objects.get(pk=value)
        except Category.DoesNotExist:
            return queryset.none()
        return queryset.filter(category_id__in=category.descendant_ids())

    def filter_has_datasheet(self, queryset, name, value):
        cond = ~Q(datasheet_url="") | ~Q(datasheet_file="")
        return queryset.filter(cond) if value else queryset.exclude(cond)

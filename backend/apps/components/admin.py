from django.contrib import admin

from .models import Category, Component, ComponentAlias, ComponentSpecification, Package, SpecificationDefinition


class SpecInline(admin.TabularInline):
    model = ComponentSpecification
    extra = 0


class AliasInline(admin.TabularInline):
    model = ComponentAlias
    extra = 0
    exclude = ("alias_normalized",)


@admin.register(Component)
class ComponentAdmin(admin.ModelAdmin):
    list_display = ("internal_part_number", "mpn", "name", "manufacturer", "category", "status", "lifecycle_status")
    list_filter = ("status", "lifecycle_status", "category")
    search_fields = ("internal_part_number", "mpn", "name")
    inlines = [SpecInline, AliasInline]
    readonly_fields = ("search_document", "mpn_normalized")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "parent")


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ("name", "mounting_type", "pin_count")


@admin.register(SpecificationDefinition)
class SpecificationDefinitionAdmin(admin.ModelAdmin):
    list_display = ("name", "key", "category", "data_type", "unit", "is_required", "is_active")
    list_filter = ("category", "data_type")

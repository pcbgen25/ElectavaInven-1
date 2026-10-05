from django.contrib import admin

from .models import Manufacturer


@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ("name", "short_name", "country", "deleted_at")
    search_fields = ("name", "short_name")

    def get_queryset(self, request):
        return Manufacturer.all_objects.all()

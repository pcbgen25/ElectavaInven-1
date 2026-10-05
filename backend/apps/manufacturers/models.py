from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower

from apps.core.models import AuthoredModel, SoftDeleteModel, TimeStampedModel


class Manufacturer(TimeStampedModel, SoftDeleteModel, AuthoredModel):
    name = models.CharField(max_length=150)
    short_name = models.CharField(max_length=50, blank=True, help_text="Common abbreviation, e.g. TI, ST.")
    website = models.URLField(blank=True)
    country = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"), condition=Q(deleted_at__isnull=True), name="manufacturer_name_ci_unique_alive"
            )
        ]

    def __str__(self) -> str:
        return self.name

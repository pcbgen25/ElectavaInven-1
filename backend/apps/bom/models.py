from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.components.models import Component
from apps.core.models import AuthoredModel, SoftDeleteModel, TimeStampedModel
from apps.projects.models import Project

LOCKED_REVISION_STATUSES = ("RELEASED", "OBSOLETE")


class BOM(TimeStampedModel, SoftDeleteModel, AuthoredModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        REVIEW = "REVIEW", "In Review"
        RELEASED = "RELEASED", "Released"
        OBSOLETE = "OBSOLETE", "Obsolete"

    # PROTECT: a project is soft-deleted, never hard-deleted, so its BOM history survives.
    project = models.ForeignKey(Project, on_delete=models.PROTECT, related_name="boms")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "BOM"
        verbose_name_plural = "BOMs"

    def __str__(self):
        return f"{self.project.code} - {self.name}"


class BOMRevision(TimeStampedModel, AuthoredModel):
    """A released (or obsolete) revision is immutable; the only allowed change is RELEASED -> OBSOLETE."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        REVIEW = "REVIEW", "In Review"
        RELEASED = "RELEASED", "Released"
        OBSOLETE = "OBSOLETE", "Obsolete"

    bom = models.ForeignKey(BOM, on_delete=models.PROTECT, related_name="revisions")
    revision_number = models.CharField(max_length=20, help_text="e.g. REV A, REV B")
    revision_name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    released_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="released_boms")
    released_at = models.DateTimeField(null=True, blank=True)

    _FROZEN = ("bom_id", "revision_number", "revision_name", "description", "released_by_id", "released_at")

    class Meta:
        ordering = ["-created_at"]
        unique_together = (("bom", "revision_number"),)
        constraints = [
            models.CheckConstraint(
                condition=~Q(status="RELEASED") | (Q(released_at__isnull=False) & Q(released_by__isnull=False)),
                name="bom_revision_released_has_releaser",
            ),
        ]

    def __str__(self):
        return f"{self.bom.name} - {self.revision_number}"

    @property
    def is_locked(self) -> bool:
        return self.status in LOCKED_REVISION_STATUSES

    def save(self, *args, **kwargs):
        if self.pk is not None and not self._state.adding:
            old = BOMRevision.objects.filter(pk=self.pk).first()
            if old is not None and old.status in LOCKED_REVISION_STATUSES:
                changed = [f for f in self._FROZEN if getattr(old, f) != getattr(self, f)]
                allowed_status = self.status == old.status or (old.status == "RELEASED" and self.status == "OBSOLETE")
                if changed or not allowed_status:
                    raise ValidationError("Cannot modify a released BOM revision. Create a new revision instead.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status in LOCKED_REVISION_STATUSES:
            raise ValidationError("Cannot delete a released BOM revision.")
        return super().delete(*args, **kwargs)


class BOMItem(TimeStampedModel):
    # CASCADE only removes items of a deletable (draft) revision; released revisions refuse deletion.
    revision = models.ForeignKey(BOMRevision, on_delete=models.CASCADE, related_name="items")
    component = models.ForeignKey(Component, on_delete=models.PROTECT, related_name="bom_usages")

    # Store references like ["R1", "R2", "R3"] efficiently
    designators = ArrayField(models.CharField(max_length=50), default=list, blank=True)

    quantity = models.DecimalField(max_digits=10, decimal_places=4, default=1.0)
    description = models.CharField(max_length=500, blank=True)
    notes = models.TextField(blank=True)

    unit_cost_snapshot = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    total_cost_snapshot = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name="bom_item_quantity_positive")]

    def __str__(self):
        return f"{self.quantity}x {self.component.internal_part_number}"

    def _guard(self):
        status = BOMRevision.objects.filter(pk=self.revision_id).values_list("status", flat=True).first()
        if status in LOCKED_REVISION_STATUSES:
            raise ValidationError("Cannot modify items of a released BOM revision. Create a new revision instead.")

    def save(self, *args, **kwargs):
        self._guard()
        if self.pk is not None and not self._state.adding:
            old_rev = BOMItem.objects.filter(pk=self.pk).values_list("revision_id", flat=True).first()
            if old_rev is not None and old_rev != self.revision_id:
                raise ValidationError("A BOM item cannot be moved to another revision.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self._guard()
        return super().delete(*args, **kwargs)

import os

# Create __init__.py files
for d in ['apps/projects', 'apps/projects/migrations', 'apps/bom', 'apps/bom/migrations']:
    open(f'backend/{d}/__init__.py', 'w').close()

# apps/projects/apps.py
with open('backend/apps/projects/apps.py', 'w') as f:
    f.write('''from django.apps import AppConfig

class ProjectsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.projects"
''')

# apps/bom/apps.py
with open('backend/apps/bom/apps.py', 'w') as f:
    f.write('''from django.apps import AppConfig

class BomConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.bom"
''')

# apps/projects/models.py
with open('backend/apps/projects/models.py', 'w') as f:
    f.write('''from django.conf import settings
from django.db import models
from apps.core.models import AuthoredModel, SoftDeleteModel, TimeStampedModel

class Project(TimeStampedModel, SoftDeleteModel, AuthoredModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        ON_HOLD = "ON_HOLD", "On Hold"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    code = models.CharField(max_length=50, unique=True, help_text="e.g. PCBGEN_CK_UCB_020-01")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    customer = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    start_date = models.DateField(null=True, blank=True)
    target_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.code} - {self.name}"

class ProjectMember(TimeStampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_memberships")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = (("project", "user"),)

    def __str__(self):
        return f"{self.user} in {self.project}"
''')

# apps/bom/models.py
with open('backend/apps/bom/models.py', 'w') as f:
    f.write('''from django.conf import settings
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db import models
from apps.core.models import AuthoredModel, SoftDeleteModel, TimeStampedModel
from apps.projects.models import Project
from apps.components.models import Component

class BOM(TimeStampedModel, SoftDeleteModel, AuthoredModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        REVIEW = "REVIEW", "In Review"
        RELEASED = "RELEASED", "Released"
        OBSOLETE = "OBSOLETE", "Obsolete"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="boms")
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
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        REVIEW = "REVIEW", "In Review"
        RELEASED = "RELEASED", "Released"
        OBSOLETE = "OBSOLETE", "Obsolete"

    bom = models.ForeignKey(BOM, on_delete=models.CASCADE, related_name="revisions")
    revision_number = models.CharField(max_length=20, help_text="e.g. REV A, REV B")
    revision_name = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    
    released_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="released_boms")
    released_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = (("bom", "revision_number"),)

    def __str__(self):
        return f"{self.bom.name} - {self.revision_number}"

    def clean(self):
        if self.pk:
            old = BOMRevision.objects.get(pk=self.pk)
            if old.status == self.Status.RELEASED and self.status == self.Status.RELEASED:
                # Basic immutability check
                if old.revision_number != self.revision_number:
                    raise ValidationError("Cannot modify a released BOM revision.")


class BOMItem(TimeStampedModel):
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

    def __str__(self):
        return f"{self.quantity}x {self.component.internal_part_number}"
''')

print("Models created.")

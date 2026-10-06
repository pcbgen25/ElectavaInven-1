from django.conf import settings
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

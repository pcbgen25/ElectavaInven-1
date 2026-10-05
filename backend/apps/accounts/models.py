from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower

from apps.core.models import TimeStampedModel

from .rbac_catalog import SUPER_ADMIN


class Permission(models.Model):
    """Business permission, e.g. ``component.create``. Not Django's model permission."""

    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=200)
    module = models.CharField(max_length=50, db_index=True)

    class Meta:
        ordering = ["module", "code"]

    def __str__(self) -> str:
        return self.code


class Role(TimeStampedModel):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=False, help_text="System roles cannot be deleted or renamed.")
    permissions = models.ManyToManyField(Permission, related_name="roles", blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.code


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)  # None -> unusable password
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra["is_staff"] = True
        extra["is_superuser"] = True
        user = self._create_user(email, password, **extra)
        role = Role.objects.filter(code=SUPER_ADMIN).first()
        if role:
            user.roles.add(role)
        return user


class User(AbstractUser):
    username = None
    email = models.EmailField("email address", unique=True)
    job_title = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    roles = models.ManyToManyField(Role, related_name="users", blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta:
        ordering = ["first_name", "last_name", "email"]
        constraints = [models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique")]

    def __str__(self) -> str:
        return self.email

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.email

    # --- RBAC ---------------------------------------------------------------
    @property
    def is_super_admin(self) -> bool:
        if self.is_superuser:
            return True
        return SUPER_ADMIN in self.get_role_codes()

    def get_role_codes(self) -> frozenset[str]:
        if not hasattr(self, "_role_cache"):
            self._role_cache = frozenset(self.roles.values_list("code", flat=True)) if self.pk else frozenset()
        return self._role_cache

    def get_rbac_permissions(self) -> frozenset[str]:
        if not hasattr(self, "_rbac_perm_cache"):
            if not self.is_active or not self.pk:
                perms: frozenset[str] = frozenset()
            elif self.is_super_admin:
                perms = frozenset(Permission.objects.values_list("code", flat=True))
            else:
                perms = frozenset(
                    Permission.objects.filter(roles__users=self).values_list("code", flat=True).distinct()
                )
            self._rbac_perm_cache = perms
        return self._rbac_perm_cache

    def has_rbac_permission(self, code: str) -> bool:
        if not self.is_active:
            return False
        if self.is_super_admin:
            return True
        return code in self.get_rbac_permissions()

    def clear_rbac_cache(self) -> None:
        for attr in ("_role_cache", "_rbac_perm_cache"):
            if hasattr(self, attr):
                delattr(self, attr)

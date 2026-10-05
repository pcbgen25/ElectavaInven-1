from django.contrib.postgres.indexes import GinIndex, OpClass
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower, Upper

from apps.core.models import AuthoredModel, SoftDeleteModel, TimeStampedModel

PN_PREFIX_VALIDATOR = RegexValidator(
    r"^[A-Z0-9]+(-[A-Z0-9]+)*$", "Use upper-case letters, digits and single hyphens, e.g. IC-CAN."
)


class Category(TimeStampedModel, SoftDeleteModel, AuthoredModel):
    """Hierarchical component category. ``code`` is the internal part-number prefix."""

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, validators=[PN_PREFIX_VALIDATOR], help_text="Part number prefix, e.g. IC-CAN")
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    description = models.TextField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(fields=["code"], condition=Q(deleted_at__isnull=True), name="category_code_unique_alive"),
            models.UniqueConstraint(
                Lower("name"), "parent", condition=Q(deleted_at__isnull=True), nulls_distinct=False,
                name="category_name_parent_unique_alive",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def ancestors(self) -> list["Category"]:
        chain, node, seen = [], self.parent, {self.pk}
        while node is not None and node.pk not in seen:
            chain.append(node)
            seen.add(node.pk)
            node = node.parent
        return list(reversed(chain))

    @property
    def full_path(self) -> str:
        return " / ".join([c.name for c in self.ancestors()] + [self.name])

    def descendant_ids(self) -> list[int]:
        ids, frontier = [self.pk], [self.pk]
        while frontier:
            frontier = list(Category.objects.filter(parent_id__in=frontier).values_list("pk", flat=True))
            ids.extend(frontier)
        return ids


class Package(TimeStampedModel, SoftDeleteModel, AuthoredModel):
    class MountingType(models.TextChoices):
        SMD = "SMD", "Surface mount"
        THT = "THT", "Through hole"
        OTHER = "OTHER", "Other"

    name = models.CharField(max_length=60, help_text="e.g. SOIC-8, 0603, LQFP-100")
    mounting_type = models.CharField(max_length=10, choices=MountingType.choices, default=MountingType.SMD)
    pin_count = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), condition=Q(deleted_at__isnull=True), name="package_name_ci_unique_alive")
        ]

    def __str__(self) -> str:
        return self.name


class PartNumberSequence(models.Model):
    """Per-prefix counter for internal part numbers. Locked with SELECT FOR UPDATE."""

    prefix = models.CharField(max_length=20, unique=True)
    last_value = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f"{self.prefix}:{self.last_value}"


class Component(TimeStampedModel, SoftDeleteModel, AuthoredModel):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"

    class Lifecycle(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        NRND = "NRND", "Not recommended for new designs"
        LAST_TIME_BUY = "LAST_TIME_BUY", "Last time buy"
        OBSOLETE = "OBSOLETE", "Obsolete"
        UNKNOWN = "UNKNOWN", "Unknown"

    internal_part_number = models.CharField(max_length=40, unique=True, help_text="e.g. IC-CAN-00001. Never reused.")
    mpn = models.CharField("manufacturer part number", max_length=100, blank=True)
    mpn_normalized = models.CharField(max_length=100, blank=True, db_index=True, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="components")
    manufacturer = models.ForeignKey(
        "manufacturers.Manufacturer", null=True, blank=True, on_delete=models.PROTECT, related_name="components"
    )
    package = models.ForeignKey(Package, null=True, blank=True, on_delete=models.PROTECT, related_name="components")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE, db_index=True)
    lifecycle_status = models.CharField(
        max_length=15, choices=Lifecycle.choices, default=Lifecycle.UNKNOWN, db_index=True
    )
    is_rohs = models.BooleanField(null=True, blank=True, help_text="Null = unknown")
    is_reach = models.BooleanField(null=True, blank=True, help_text="Null = unknown")
    datasheet_url = models.URLField(max_length=500, blank=True)
    datasheet_file = models.FileField(upload_to="components/datasheets/", blank=True, max_length=255)
    image = models.ImageField(upload_to="components/images/", blank=True, max_length=255)
    notes = models.TextField(blank=True)
    search_document = models.TextField(blank=True, editable=False)

    class Meta:
        ordering = ["internal_part_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["manufacturer", "mpn_normalized"],
                condition=Q(deleted_at__isnull=True) & ~Q(mpn_normalized=""),
                name="component_mfr_mpn_unique_alive",
            )
        ]
        indexes = [
            GinIndex(OpClass(Upper("search_document"), name="gin_trgm_ops"), name="component_search_trgm"),
            models.Index(fields=["category", "status"], name="component_cat_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.internal_part_number} {self.mpn}".strip()


class ComponentAlias(TimeStampedModel):
    class AliasType(models.TextChoices):
        ALTERNATE_MPN = "ALTERNATE_MPN", "Alternate MPN / ordering code"
        LEGACY_PN = "LEGACY_PN", "Legacy internal PN"
        CUSTOMER_PN = "CUSTOMER_PN", "Customer PN"
        KICAD_VALUE = "KICAD_VALUE", "KiCad value / symbol name"
        OTHER = "OTHER", "Other"

    component = models.ForeignKey(Component, on_delete=models.CASCADE, related_name="aliases")
    alias = models.CharField(max_length=150)
    alias_normalized = models.CharField(max_length=150, db_index=True, editable=False)
    alias_type = models.CharField(max_length=20, choices=AliasType.choices, default=AliasType.OTHER)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["alias"]
        constraints = [
            models.UniqueConstraint(fields=["component", "alias_normalized"], name="component_alias_unique")
        ]

    def __str__(self) -> str:
        return self.alias


class SpecificationDefinition(TimeStampedModel):
    """A specification a category's components may carry (inherited by sub-categories)."""

    class DataType(models.TextChoices):
        STRING = "STRING", "Text"
        INTEGER = "INTEGER", "Integer"
        DECIMAL = "DECIMAL", "Decimal"
        BOOLEAN = "BOOLEAN", "Yes / No"
        ENUM = "ENUM", "Choice list"

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="specification_definitions")
    key = models.SlugField(max_length=50, help_text="Stable machine key, e.g. capacitance")
    name = models.CharField(max_length=100)
    data_type = models.CharField(max_length=10, choices=DataType.choices)
    unit = models.CharField(max_length=20, blank=True, help_text="Base unit, e.g. F, Ω, V, W, %, KB")
    use_si_prefix = models.BooleanField(
        default=False, help_text="Accept/display SI prefixes (p, n, µ, m, k, M) for DECIMAL values"
    )
    enum_choices = models.JSONField(default=list, blank=True, help_text="Allowed values for ENUM")
    is_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    help_text = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["category_id", "sort_order", "name"]
        constraints = [models.UniqueConstraint(fields=["category", "key"], name="specdef_category_key_unique")]

    def __str__(self) -> str:
        return f"{self.category} · {self.name}"


class ComponentSpecification(TimeStampedModel):
    """Typed value of one specification for one component."""

    component = models.ForeignKey(Component, on_delete=models.CASCADE, related_name="specifications")
    definition = models.ForeignKey(SpecificationDefinition, on_delete=models.PROTECT, related_name="values")
    value_string = models.CharField(max_length=255, blank=True)
    value_integer = models.BigIntegerField(null=True, blank=True)
    value_decimal = models.DecimalField(max_digits=34, decimal_places=18, null=True, blank=True)
    value_boolean = models.BooleanField(null=True, blank=True)

    class Meta:
        ordering = ["definition__sort_order", "definition__name"]
        constraints = [
            models.UniqueConstraint(fields=["component", "definition"], name="component_spec_unique"),
        ]
        indexes = [
            models.Index(fields=["definition", "value_decimal"], name="spec_def_decimal_idx"),
            models.Index(fields=["definition", "value_integer"], name="spec_def_integer_idx"),
            models.Index(fields=["definition", "value_string"], name="spec_def_string_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.component_id}:{self.definition.key}"

    @property
    def value(self):
        dt = SpecificationDefinition.DataType
        return {
            dt.STRING: self.value_string,
            dt.ENUM: self.value_string,
            dt.INTEGER: self.value_integer,
            dt.DECIMAL: self.value_decimal,
            dt.BOOLEAN: self.value_boolean,
        }[self.definition.data_type]

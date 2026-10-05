from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.manufacturers.models import Manufacturer

from . import services
from .models import (
    PN_PREFIX_VALIDATOR,
    Category,
    Component,
    ComponentAlias,
    ComponentSpecification,
    Package,
    SpecificationDefinition,
)


# --- master data ------------------------------------------------------------
class CategorySerializer(serializers.ModelSerializer):
    full_path = serializers.CharField(read_only=True)
    component_count = serializers.IntegerField(read_only=True)
    parent_name = serializers.CharField(source="parent.name", read_only=True, default=None)

    class Meta:
        model = Category
        fields = [
            "id", "name", "code", "parent", "parent_name", "full_path", "description", "sort_order",
            "component_count", "created_at", "updated_at",
        ]
        extra_kwargs = {"code": {"validators": []}}  # validated after upper-casing in validate_code

    def validate_code(self, value: str) -> str:
        value = value.strip().upper()
        try:
            PN_PREFIX_VALIDATOR(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        qs = Category.objects.filter(code=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Another category already uses this code.")
        if self.instance and self.instance.code != value and self.instance.components.exists():
            raise serializers.ValidationError("Code cannot change once components use it (part numbers depend on it).")
        return value

    def validate(self, attrs):
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        name = " ".join(attrs.get("name", getattr(self.instance, "name", "")).split())
        attrs["name"] = name
        if self.instance and parent:
            if parent.pk == self.instance.pk or parent.pk in self.instance.descendant_ids():
                raise serializers.ValidationError({"parent": ["A category cannot be moved under itself."]})
        qs = Category.objects.filter(parent=parent, name__iexact=name)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError({"name": ["A category with this name already exists here."]})
        return attrs


class PackageSerializer(serializers.ModelSerializer):
    component_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Package
        fields = ["id", "name", "mounting_type", "pin_count", "description", "component_count", "created_at", "updated_at"]

    def validate_name(self, value: str) -> str:
        value = value.strip()
        qs = Package.objects.filter(name__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A package with this name already exists.")
        return value


class SpecificationDefinitionSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    value_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = SpecificationDefinition
        fields = [
            "id", "category", "category_name", "key", "name", "data_type", "unit", "use_si_prefix",
            "enum_choices", "is_required", "is_active", "sort_order", "help_text", "value_count",
        ]

    def validate_enum_choices(self, value):
        if not isinstance(value, list) or not all(isinstance(v, (str, int, float)) for v in value):
            raise serializers.ValidationError("Must be a list of values.")
        cleaned = [str(v).strip() for v in value if str(v).strip()]
        if len({c.lower() for c in cleaned}) != len(cleaned):
            raise serializers.ValidationError("Choices must be unique.")
        return cleaned

    def validate(self, attrs):
        inst = self.instance
        category = attrs.get("category", getattr(inst, "category", None))
        data_type = attrs.get("data_type", getattr(inst, "data_type", None))
        key = attrs.get("key", getattr(inst, "key", None))
        if data_type == SpecificationDefinition.DataType.ENUM and not attrs.get("enum_choices", getattr(inst, "enum_choices", [])):
            raise serializers.ValidationError({"enum_choices": ["Choice list definitions need at least one choice."]})
        if attrs.get("use_si_prefix") and data_type not in ("DECIMAL", "INTEGER"):
            raise serializers.ValidationError({"use_si_prefix": ["SI prefixes only apply to numeric values."]})
        if inst and inst.values.exists():
            if "data_type" in attrs and attrs["data_type"] != inst.data_type:
                raise serializers.ValidationError({"data_type": ["Cannot change the type while components have values."]})
            if "category" in attrs and attrs["category"].pk != inst.category_id:
                raise serializers.ValidationError({"category": ["Cannot move a definition that already has values."]})
        # A key must be unique along the category's ancestor/descendant line.
        if category and key:
            related = [c.pk for c in category.ancestors()] + category.descendant_ids()
            qs = SpecificationDefinition.objects.filter(category_id__in=related, key=key)
            if inst:
                qs = qs.exclude(pk=inst.pk)
            if qs.exists():
                raise serializers.ValidationError({"key": ["This key is already defined in this category line."]})
        return attrs


# --- components -------------------------------------------------------------
class _Ref(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class ComponentListSerializer(serializers.ModelSerializer):
    category = _Ref(read_only=True)
    manufacturer = _Ref(read_only=True, allow_null=True)
    package = _Ref(read_only=True, allow_null=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Component
        fields = [
            "id", "internal_part_number", "mpn", "name", "description", "category", "manufacturer", "package",
            "status", "lifecycle_status", "is_rohs", "is_reach", "image_url", "updated_at",
        ]

    def get_image_url(self, obj) -> str | None:
        return obj.image.url if obj.image else None


class SpecificationValueSerializer(serializers.ModelSerializer):
    definition = serializers.IntegerField(source="definition_id")
    key = serializers.CharField(source="definition.key")
    name = serializers.CharField(source="definition.name")
    data_type = serializers.CharField(source="definition.data_type")
    unit = serializers.CharField(source="definition.unit")
    value = serializers.SerializerMethodField()
    display_value = serializers.SerializerMethodField()

    class Meta:
        model = ComponentSpecification
        fields = ["definition", "key", "name", "data_type", "unit", "value", "display_value"]

    def get_value(self, obj):
        v = obj.value
        return str(v) if v is not None and obj.definition.data_type == "DECIMAL" else v

    def get_display_value(self, obj) -> str:
        return services.display_spec_value(obj)


class AliasSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComponentAlias
        fields = ["id", "alias", "alias_type", "notes"]


class ComponentDetailSerializer(ComponentListSerializer):
    specifications = SpecificationValueSerializer(many=True, read_only=True)
    aliases = AliasSerializer(many=True, read_only=True)
    category_path = serializers.CharField(source="category.full_path", read_only=True)
    datasheet_file_url = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default=None)
    updated_by_name = serializers.CharField(source="updated_by.full_name", read_only=True, default=None)

    class Meta(ComponentListSerializer.Meta):
        fields = ComponentListSerializer.Meta.fields + [
            "category_path", "datasheet_url", "datasheet_file_url", "notes", "specifications", "aliases",
            "created_by_name", "updated_by_name", "created_at",
        ]

    def get_datasheet_file_url(self, obj) -> str | None:
        return obj.datasheet_file.url if obj.datasheet_file else None


class SpecInputSerializer(serializers.Serializer):
    definition = serializers.IntegerField()
    value = serializers.JSONField(allow_null=True)


class AliasInputSerializer(serializers.Serializer):
    alias = serializers.CharField(max_length=150)
    alias_type = serializers.ChoiceField(choices=ComponentAlias.AliasType.choices, required=False)
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True)


class ComponentWriteSerializer(serializers.ModelSerializer):
    internal_part_number = serializers.CharField(
        max_length=40, required=False, allow_blank=True, help_text="Leave blank to auto-generate from the category code."
    )
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all())
    manufacturer = serializers.PrimaryKeyRelatedField(queryset=Manufacturer.objects.all(), allow_null=True, required=False)
    package = serializers.PrimaryKeyRelatedField(queryset=Package.objects.all(), allow_null=True, required=False)
    specifications = SpecInputSerializer(many=True, required=False)
    aliases = AliasInputSerializer(many=True, required=False)

    class Meta:
        model = Component
        fields = [
            "internal_part_number", "mpn", "name", "description", "category", "manufacturer", "package",
            "status", "lifecycle_status", "is_rohs", "is_reach", "datasheet_url", "notes",
            "specifications", "aliases",
        ]
        extra_kwargs = {"name": {"required": True}}

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Name is required.")
        return value

    def validate_internal_part_number(self, value: str) -> str:
        value = value.strip().upper()
        if value and not all(ch.isalnum() or ch in "-_." for ch in value):
            raise serializers.ValidationError("Use letters, digits, '-', '_' or '.' only.")
        return value

    def validate(self, attrs):
        if attrs.get("mpn") and not attrs.get("manufacturer", getattr(self.instance, "manufacturer", None)):
            raise serializers.ValidationError({"manufacturer": ["Select the manufacturer for this MPN."]})
        return attrs

    def create(self, validated_data):
        specs = validated_data.pop("specifications", None)
        aliases = validated_data.pop("aliases", None)
        request = self.context["request"]
        return services.create_component(
            data=validated_data, specifications=specs, aliases=aliases, user=request.user, request=request
        )

    def update(self, instance, validated_data):
        specs = validated_data.pop("specifications", None)
        aliases = validated_data.pop("aliases", None)
        request = self.context["request"]
        return services.update_component(
            instance, data=validated_data, specifications=specs, aliases=aliases, user=request.user, request=request
        )


class FileUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

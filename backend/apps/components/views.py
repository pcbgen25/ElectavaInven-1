from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apps.audit.mixins import AuditedModelViewSetMixin
from apps.core.exceptions import Conflict

from . import services
from .filters import ComponentFilter
from .models import Category, Component, Package, SpecificationDefinition
from .serializers import (
    CategorySerializer,
    ComponentDetailSerializer,
    ComponentListSerializer,
    ComponentWriteSerializer,
    FileUploadSerializer,
    PackageSerializer,
    SpecificationDefinitionSerializer,
)

MASTERDATA_PERMS = {
    "list": "component.view",
    "retrieve": "component.view",
    "create": "masterdata.manage",
    "update": "masterdata.manage",
    "partial_update": "masterdata.manage",
    "destroy": "masterdata.manage",
}
ALIVE = Q(components__deleted_at__isnull=True)


class CategoryViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    filterset_fields = ["parent"]
    search_fields = ["name", "code", "description"]
    ordering_fields = ["name", "code", "sort_order", "component_count"]
    ordering = ["sort_order", "name"]
    pagination_class = None  # category trees are small; the UI needs the full tree
    required_permissions = {**MASTERDATA_PERMS, "specification_definitions": "component.view"}

    def get_queryset(self):
        return Category.objects.select_related("parent", "parent__parent").annotate(
            component_count=Count("components", filter=ALIVE, distinct=True)
        )

    def perform_update(self, serializer):
        old = (serializer.instance.name, serializer.instance.parent_id)
        super().perform_update(serializer)
        if (serializer.instance.name, serializer.instance.parent_id) != old:
            services.rebuild_search_documents_for(category=serializer.instance)

    def check_can_delete(self, instance):
        if instance.children.exists():
            raise Conflict("Category has sub-categories. Move or delete them first.")
        if instance.components.exists():
            raise Conflict("Category has components. Move them to another category first.")

    @extend_schema(
        responses=SpecificationDefinitionSerializer(many=True),
        parameters=[OpenApiParameter("include_inactive", bool, required=False)],
    )
    @action(detail=True, methods=["get"], url_path="specification-definitions")
    def specification_definitions(self, request, pk=None):
        """Effective definitions for this category, including inherited ones."""
        include_inactive = request.query_params.get("include_inactive") in ("1", "true", "True")
        defs = services.effective_definitions(self.get_object(), include_inactive=include_inactive)
        return Response(SpecificationDefinitionSerializer(defs, many=True).data)


class PackageViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = PackageSerializer
    filterset_fields = ["mounting_type"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "pin_count", "component_count"]
    ordering = ["name"]
    required_permissions = MASTERDATA_PERMS

    def get_queryset(self):
        return Package.objects.annotate(component_count=Count("components", filter=ALIVE, distinct=True))

    def perform_update(self, serializer):
        old_name = serializer.instance.name
        super().perform_update(serializer)
        if serializer.instance.name != old_name:
            services.rebuild_search_documents_for(package=serializer.instance)

    def check_can_delete(self, instance):
        if instance.components.filter(deleted_at__isnull=True).exists():
            raise Conflict("Package is used by components.")


class SpecificationDefinitionViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = SpecificationDefinitionSerializer
    filterset_fields = ["category", "data_type", "is_active"]
    search_fields = ["name", "key"]
    ordering = ["category_id", "sort_order", "name"]
    required_permissions = MASTERDATA_PERMS

    def get_queryset(self):
        return SpecificationDefinition.objects.select_related("category").annotate(value_count=Count("values"))

    def check_can_delete(self, instance):
        if instance.values.exists():
            raise Conflict("Components have values for this specification. Deactivate it instead.")


class ComponentViewSet(viewsets.ModelViewSet):
    filterset_class = ComponentFilter
    search_fields = ["search_document"]
    ordering_fields = [
        "internal_part_number", "mpn", "name", "status", "lifecycle_status", "created_at", "updated_at",
        "manufacturer__name", "category__name", "package__name",
    ]
    ordering = ["internal_part_number"]
    required_permissions = {
        "list": "component.view",
        "retrieve": "component.view",
        "create": "component.create",
        "update": "component.edit",
        "partial_update": "component.edit",
        "destroy": "component.delete",
        "upload_image": "component.edit",
        "delete_image": "component.edit",
        "upload_datasheet": "component.edit",
        "delete_datasheet": "component.edit",
    }

    def get_queryset(self):
        qs = Component.objects.select_related("category", "manufacturer", "package")
        if self.action == "retrieve":
            qs = qs.select_related("category__parent", "created_by", "updated_by").prefetch_related(
                "aliases", "specifications__definition"
            )
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return ComponentListSerializer
        if self.action in ("create", "update", "partial_update"):
            return ComponentWriteSerializer
        return ComponentDetailSerializer

    def _detail(self, component, code=status.HTTP_200_OK):
        fresh = self.get_queryset().select_related("category__parent", "created_by", "updated_by").prefetch_related(
            "aliases", "specifications__definition"
        ).get(pk=component.pk)
        return Response(ComponentDetailSerializer(fresh, context={"request": self.request}).data, status=code)

    @extend_schema(request=ComponentWriteSerializer, responses={201: ComponentDetailSerializer})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return self._detail(serializer.save(), status.HTTP_201_CREATED)

    @extend_schema(request=ComponentWriteSerializer, responses={200: ComponentDetailSerializer})
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        return self._detail(serializer.save())

    def perform_destroy(self, instance):
        services.delete_component(instance, user=self.request.user, request=self.request)

    def _upload(self, request, field):
        serializer = FileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        component = services.attach_file(
            self.get_object(), field, serializer.validated_data["file"], user=request.user, request=request
        )
        return self._detail(component)

    def _remove(self, request, field):
        component = services.remove_file(self.get_object(), field, user=request.user, request=request)
        return self._detail(component)

    @extend_schema(request={"multipart/form-data": FileUploadSerializer}, responses=ComponentDetailSerializer)
    @action(detail=True, methods=["post"], url_path="image", parser_classes=[MultiPartParser])
    def upload_image(self, request, pk=None):
        return self._upload(request, "image")

    @extend_schema(request=None, responses=ComponentDetailSerializer)
    @upload_image.mapping.delete
    def delete_image(self, request, pk=None):
        return self._remove(request, "image")

    @extend_schema(request={"multipart/form-data": FileUploadSerializer}, responses=ComponentDetailSerializer)
    @action(detail=True, methods=["post"], url_path="datasheet", parser_classes=[MultiPartParser])
    def upload_datasheet(self, request, pk=None):
        return self._upload(request, "datasheet_file")

    @extend_schema(request=None, responses=ComponentDetailSerializer)
    @upload_datasheet.mapping.delete
    def delete_datasheet(self, request, pk=None):
        return self._remove(request, "datasheet_file")

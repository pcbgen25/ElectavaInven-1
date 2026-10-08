"""BOM REST API. Released revisions are immutable; enforcement lives in serializers, services and models."""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apps.audit.mixins import AuditedModelViewSetMixin
from apps.inventory.services import bom_inventory_availability

from . import services
from .models import BOM, BOMItem, BOMRevision
from .serializers import (
    BOMImportConfirmSerializer,
    BOMImportPreviewSerializer,
    BOMItemSerializer,
    BOMRevisionListSerializer,
    BOMRevisionSerializer,
    BOMSerializer,
)


class BOMViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """DELETE soft-deletes the BOM; revisions (including released ones) are preserved."""

    serializer_class = BOMSerializer
    filterset_fields = ["project", "status"]
    search_fields = ["name", "description", "project__code", "project__name"]
    ordering_fields = ["name", "status", "created_at", "updated_at", "project__code"]
    ordering = ["-created_at"]
    required_permissions = {
        "list": "bom.view",
        "retrieve": "bom.view",
        "create": "bom.create",
        "update": "bom.edit",
        "partial_update": "bom.edit",
        "destroy": "bom.delete",
        "import_preview": "bom.import",
        "import_confirm": "bom.import",
    }

    def get_queryset(self):
        return BOM.objects.select_related("project", "created_by").prefetch_related("revisions")

    @extend_schema(request={"multipart/form-data": BOMImportPreviewSerializer}, responses={200: dict})
    @action(detail=False, methods=["post"], url_path="import/preview", parser_classes=[MultiPartParser])
    def import_preview(self, request):
        """Step 1-3 of the KiCad wizard: detect columns, apply mapping, match components."""
        ser = BOMImportPreviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        content = services.decode_upload(ser.validated_data["file"].read())
        columns, detected, sample = services.detect_columns(content)
        mapping = ser.validated_data.get("mapping") or None
        items = services.parse_kicad_csv(content, mapping)
        preview = services.preview_bom_import(items)
        summary = {s: sum(1 for p in preview if p["match_status"] == s)
                   for s in (services.MatchStatus.MATCHED, services.MatchStatus.UNMATCHED, services.MatchStatus.AMBIGUOUS)}
        return Response({
            "columns": columns,
            "detected_mapping": detected,
            "mapping": {**detected, **(mapping or {})},
            "sample_rows": sample,
            "items": preview,
            "summary": {**summary, "total": len(preview)},
        })

    @extend_schema(request=BOMImportConfirmSerializer, responses={201: BOMSerializer})
    @action(detail=False, methods=["post"], url_path="import/confirm")
    def import_confirm(self, request):
        """Step 5: create the BOM and REV A from resolved rows."""
        ser = BOMImportConfirmSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        bom = services.create_bom_from_import(d["project"], d["name"], request.user, d["items"], d["description"], request)
        return Response(BOMSerializer(self.get_queryset().get(pk=bom.pk)).data, status=status.HTTP_201_CREATED)


class BOMRevisionViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = BOMRevisionSerializer
    filterset_fields = ["bom", "status"]
    search_fields = ["revision_number", "revision_name", "bom__name"]
    ordering_fields = ["created_at", "revision_number", "released_at"]
    ordering = ["-created_at"]
    required_permissions = {
        "list": "bom.view",
        "retrieve": "bom.view",
        "compare": "bom.view",
        "availability": "bom.view",
        "cost": "bom.view",
        "create": "bom.create",
        "update": "bom.edit",
        "partial_update": "bom.edit",
        "destroy": "bom.edit",
        "release": "bom.release",
    }

    def get_queryset(self):
        qs = BOMRevision.objects.select_related("bom__project", "created_by", "released_by")
        if self.action == "list":
            return qs.annotate(item_count=Count("items"))
        return qs.prefetch_related("items__component")

    def get_serializer_class(self):
        return BOMRevisionListSerializer if self.action == "list" else BOMRevisionSerializer

    def check_can_delete(self, instance):
        try:
            services.ensure_revision_editable(instance)
        except DjangoValidationError as exc:
            raise ValidationError({"detail": exc.messages}) from None

    @extend_schema(request=None, responses=BOMRevisionSerializer)
    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        revision = services.release_revision(self.get_object(), request.user, request)
        return Response(BOMRevisionSerializer(self.get_queryset().get(pk=revision.pk)).data)

    @extend_schema(parameters=[OpenApiParameter("rev_a", int, required=True), OpenApiParameter("rev_b", int, required=True)],
                   responses={200: dict})
    @action(detail=False, methods=["get"])
    def compare(self, request):
        ids = {k: request.query_params.get(k, "") for k in ("rev_a", "rev_b")}
        bad = [k for k, v in ids.items() if not v.isdigit()]
        if bad:
            raise ValidationError({k: "A revision id is required." for k in bad})
        rev_a = get_object_or_404(BOMRevision, pk=ids["rev_a"])
        rev_b = get_object_or_404(BOMRevision, pk=ids["rev_b"])
        return Response({
            "rev_a": BOMRevisionListSerializer(rev_a).data,
            "rev_b": BOMRevisionListSerializer(rev_b).data,
            "diff": services.compare_revisions(rev_a, rev_b),
        })

    @extend_schema(parameters=[OpenApiParameter("build_quantity", str)], responses={200: dict})
    @action(detail=True, methods=["get"])
    def availability(self, request, pk=None):
        """Required / on hand / reserved / available / shortage per component (lines aggregated)."""
        return Response(bom_inventory_availability(self.get_object(), request.query_params.get("build_quantity", "1")))

    @extend_schema(responses={200: dict})
    @action(detail=True, methods=["get"])
    def cost(self, request, pk=None):
        return Response(services.calculate_bom_cost(self.get_object()))


class BOMItemViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = BOMItemSerializer
    filterset_fields = ["revision", "component"]
    ordering = ["id"]
    required_permissions = {
        "list": "bom.view",
        "retrieve": "bom.view",
        "create": "bom.edit",
        "update": "bom.edit",
        "partial_update": "bom.edit",
        "destroy": "bom.edit",
    }

    def get_queryset(self):
        return BOMItem.objects.select_related("component", "revision")

    def _ensure_editable(self, item):
        try:
            services.ensure_revision_editable(item.revision)
        except DjangoValidationError as exc:
            raise ValidationError({"detail": exc.messages}) from None

    def perform_update(self, serializer):
        self._ensure_editable(serializer.instance)
        super().perform_update(serializer)

    def check_can_delete(self, instance):
        self._ensure_editable(instance)

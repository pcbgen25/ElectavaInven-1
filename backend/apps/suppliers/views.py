"""Views for Suppliers, Contacts, and SupplierParts."""
from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.audit import services as audit
from apps.audit.mixins import AuditedModelViewSetMixin
from apps.components.models import Component

from .filters import SupplierFilter, SupplierPartFilter
from .models import Supplier, SupplierContact, SupplierPart
from .serializers import (
    SupplierContactSerializer,
    SupplierPartSerializer,
    SupplierPriceBreakSerializer,
    SupplierPriceHistorySerializer,
    SupplierSerializer,
)
from .services import (
    check_supplier_deletable,
    compare_supplier_parts,
    create_supplier_part,
    delete_supplier_part,
    set_price_breaks,
    update_supplier_part,
)


class SupplierViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = SupplierSerializer
    filterset_class = SupplierFilter
    search_fields = ["code", "name", "legal_name", "country", "email"]
    ordering_fields = ["code", "name", "country", "status", "rating", "lead_time_days", "created_at"]
    ordering = ["name"]
    required_permissions = {
        "list": "supplier.view",
        "retrieve": "supplier.view",
        "create": "supplier.create",
        "update": "supplier.edit",
        "partial_update": "supplier.edit",
        "destroy": "supplier.delete",
        "contacts": "supplier.edit",
        "remove_contact": "supplier.edit",
    }

    def get_queryset(self):
        return (
            Supplier.objects.prefetch_related("contacts")
            .annotate(
                part_count=Count("supplier_parts", filter=Q(supplier_parts__deleted_at__isnull=True), distinct=True),
                purchase_order_count=Count("purchase_orders", distinct=True),
            )
        )

    def perform_update(self, serializer):
        old_name = serializer.instance.name
        super().perform_update(serializer)
        if serializer.instance.name != old_name:
            for part in serializer.instance.supplier_parts.select_related(
                "component__manufacturer", "component__category", "component__package"
            ):
                from apps.components.services import rebuild_search_document

                rebuild_search_document(part.component)

    def check_can_delete(self, instance: Supplier):
        check_supplier_deletable(instance)

    @extend_schema(request=SupplierContactSerializer, responses={201: SupplierContactSerializer})
    @action(detail=True, methods=["post"])
    def contacts(self, request, pk=None):
        supplier = self.get_object()
        serializer = SupplierContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.validated_data.get("is_primary"):
            supplier.contacts.filter(is_primary=True).update(is_primary=False)
        contact = serializer.save(supplier=supplier)
        audit.record_create(contact, request=request)
        return Response(SupplierContactSerializer(contact).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["delete"], url_path=r"contacts/(?P<contact_id>\d+)")
    def remove_contact(self, request, pk=None, contact_id=None):
        supplier = self.get_object()
        contact = get_object_or_404(SupplierContact, pk=contact_id, supplier=supplier)
        audit.record_delete(contact, request=request, soft=False)
        contact.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SupplierContactViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = SupplierContactSerializer
    filterset_fields = ["supplier", "is_primary"]
    search_fields = ["name", "email", "role", "phone"]
    ordering_fields = ["name", "is_primary", "created_at"]
    ordering = ["-is_primary", "name"]
    required_permissions = {
        "list": "supplier.view",
        "retrieve": "supplier.view",
        "create": "supplier.edit",
        "update": "supplier.edit",
        "partial_update": "supplier.edit",
        "destroy": "supplier.edit",
    }

    def get_queryset(self):
        return SupplierContact.objects.select_related("supplier").filter(supplier__deleted_at__isnull=True)


class SupplierPartViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierPartSerializer
    filterset_class = SupplierPartFilter
    search_fields = [
        "supplier_part_number",
        "manufacturer_part_number",
        "supplier__name",
        "supplier__code",
        "component__internal_part_number",
        "component__mpn",
        "component__name",
    ]
    ordering_fields = [
        "supplier_part_number",
        "unit_price",
        "moq",
        "lead_time_days",
        "is_preferred",
        "created_at",
    ]
    ordering = ["-is_preferred", "supplier__name", "supplier_part_number"]
    required_permissions = {
        "list": "supplier.view",
        "retrieve": "supplier.view",
        "create": "supplier.create",
        "update": "supplier.edit",
        "partial_update": "supplier.edit",
        "destroy": "supplier.delete",
        "price_breaks": "supplier.edit",
        "price_history": "supplier.view",
        "compare": "supplier.view",
    }

    def get_queryset(self):
        return (
            SupplierPart.objects.select_related("supplier", "component")
            .prefetch_related("price_breaks")
            .filter(supplier__deleted_at__isnull=True, component__deleted_at__isnull=True)
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        breaks = data.pop("price_breaks", None)
        part = create_supplier_part(data=data, price_breaks=breaks, user=request.user, request=request)
        return Response(self.get_serializer(part).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        breaks = data.pop("price_breaks", None)
        part = update_supplier_part(instance, data=data, price_breaks=breaks, user=request.user, request=request)
        return Response(self.get_serializer(part).data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        delete_supplier_part(instance, user=request.user, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=SupplierPriceBreakSerializer(many=True), responses={200: SupplierPriceBreakSerializer(many=True)})
    @action(detail=True, methods=["put", "post"], url_path="price-breaks")
    def price_breaks(self, request, pk=None):
        part = self.get_object()
        items = request.data.get("price_breaks") if isinstance(request.data, dict) else request.data
        if not isinstance(items, list):
            raise ValidationError({"price_breaks": "Expected a list of price breaks."})
        serializer = SupplierPriceBreakSerializer(data=items, many=True)
        serializer.is_valid(raise_exception=True)
        breaks = set_price_breaks(part, serializer.validated_data, user=request.user, reference="API price breaks")
        return Response(SupplierPriceBreakSerializer(breaks, many=True).data)

    @extend_schema(responses={200: SupplierPriceHistorySerializer(many=True)})
    @action(detail=True, methods=["get"], url_path="price-history")
    def price_history(self, request, pk=None):
        part = self.get_object()
        history = part.price_history.select_related("recorded_by").all()
        return Response(SupplierPriceHistorySerializer(history, many=True).data)

    @action(detail=False, methods=["get"])
    def compare(self, request):
        comp_id = request.query_params.get("component")
        if not comp_id:
            raise ValidationError({"component": "Query parameter 'component' is required."})
        component = get_object_or_404(Component, pk=comp_id)
        qty_raw = request.query_params.get("quantity", "1")
        data = compare_supplier_parts(component, Decimal(str(qty_raw)))
        return Response(data)

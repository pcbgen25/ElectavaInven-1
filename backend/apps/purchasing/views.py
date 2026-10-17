"""Views for Purchase Requests, Purchase Orders, Goods Receipts, and Purchasing Summaries."""
from __future__ import annotations

from decimal import Decimal

from django.db.models import DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.components.models import Component
from apps.core.exceptions import Conflict

from .filters import GoodsReceiptFilter, PurchaseOrderFilter, PurchaseRequestFilter
from .models import (
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseRequest,
)
from .serializers import (
    BOMShortagePRCreateSerializer,
    ConvertPRToPOSerializer,
    GoodsReceiptSerializer,
    PRReviewActionSerializer,
    PurchaseOrderSerializer,
    PurchaseRequestSerializer,
)
from .services import (
    approve_purchase_order,
    approve_purchase_request,
    cancel_purchase_order,
    cancel_purchase_request,
    close_purchase_order,
    create_goods_receipt,
    create_po_from_purchase_request,
    create_purchase_order,
    create_purchase_request,
    create_purchase_request_from_bom_shortage,
    post_goods_receipt,
    reject_purchase_request,
    send_purchase_order,
    submit_purchase_request,
    update_purchase_order,
    update_purchase_request,
)


class PurchaseRequestViewSet(viewsets.ModelViewSet):
    serializer_class = PurchaseRequestSerializer
    filterset_class = PurchaseRequestFilter
    search_fields = ["request_number", "title", "notes", "project__code", "project__name"]
    ordering_fields = ["request_number", "title", "status", "priority", "needed_by", "created_at", "updated_at"]
    ordering = ["-created_at", "-id"]
    required_permissions = {
        "list": "purchase.view",
        "retrieve": "purchase.view",
        "create": "purchase.create",
        "update": "purchase.create",
        "partial_update": "purchase.create",
        "destroy": "purchase.create",
        "submit": "purchase.create",
        "approve": "purchase.approve",
        "reject": "purchase.approve",
        "cancel": "purchase.create",
        "create_po": "purchase.order",
        "from_bom_shortage": "purchase.create",
    }

    def get_queryset(self):
        return (
            PurchaseRequest.objects.select_related(
                "project",
                "bom_revision__bom",
                "created_by",
                "submitted_by",
                "reviewed_by",
            )
            .prefetch_related(
                "items__component",
                "items__preferred_supplier",
                "items__supplier_part",
            )
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        items = data.pop("items", [])
        pr = create_purchase_request(data=data, items=items, user=request.user, request=request)
        return Response(self.get_serializer(pr).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        items = data.pop("items", None)
        pr = update_purchase_request(instance, data=data, items=items, user=request.user, request=request)
        return Response(self.get_serializer(pr).data)

    def destroy(self, request, *args, **kwargs):
        pr = self.get_object()
        if pr.status not in (PurchaseRequest.Status.DRAFT, PurchaseRequest.Status.CANCELLED):
            raise Conflict("Only DRAFT or CANCELLED purchase requests can be deleted.")
        if pr.purchase_orders.exists():
            raise Conflict("Purchase request is linked to purchase orders and cannot be deleted.")
        pr.soft_delete(request.user)
        audit.record_delete(pr, request=request, user=request.user, soft=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses={200: PurchaseRequestSerializer})
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        pr = submit_purchase_request(self.get_object(), user=request.user, request=request)
        return Response(self.get_serializer(pr).data)

    @extend_schema(request=PRReviewActionSerializer, responses={200: PurchaseRequestSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        s = PRReviewActionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        pr = approve_purchase_request(
            self.get_object(),
            user=request.user,
            notes=s.validated_data.get("notes", ""),
            request=request,
        )
        return Response(self.get_serializer(pr).data)

    @extend_schema(request=PRReviewActionSerializer, responses={200: PurchaseRequestSerializer})
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        s = PRReviewActionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        pr = reject_purchase_request(
            self.get_object(),
            user=request.user,
            notes=s.validated_data.get("notes", ""),
            request=request,
        )
        return Response(self.get_serializer(pr).data)

    @extend_schema(request=PRReviewActionSerializer, responses={200: PurchaseRequestSerializer})
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        s = PRReviewActionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        pr = cancel_purchase_request(
            self.get_object(),
            user=request.user,
            notes=s.validated_data.get("notes", ""),
            request=request,
        )
        return Response(self.get_serializer(pr).data)

    @extend_schema(request=ConvertPRToPOSerializer, responses={201: PurchaseOrderSerializer})
    @action(detail=True, methods=["post"], url_path="create-po")
    def create_po(self, request, pk=None):
        pr = self.get_object()
        s = ConvertPRToPOSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        po = create_po_from_purchase_request(
            pr,
            supplier=s.validated_data["supplier"],
            item_ids=s.validated_data.get("item_ids"),
            default_warehouse=s.validated_data.get("default_warehouse"),
            currency=s.validated_data.get("currency", ""),
            exchange_rate=s.validated_data.get("exchange_rate", Decimal("1.000000")),
            expected_delivery_date=s.validated_data.get("expected_delivery_date"),
            notes=s.validated_data.get("notes", ""),
            apply_moq=s.validated_data.get("apply_moq", False),
            user=request.user,
            request=request,
        )
        return Response(PurchaseOrderSerializer(po).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=BOMShortagePRCreateSerializer, responses={201: PurchaseRequestSerializer})
    @action(detail=False, methods=["post"], url_path="from-bom-shortage")
    def from_bom_shortage(self, request):
        s = BOMShortagePRCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        pr = create_purchase_request_from_bom_shortage(
            s.validated_data["bom_revision"],
            s.validated_data["build_quantity"],
            title=s.validated_data.get("title", ""),
            priority=s.validated_data.get("priority", PurchaseRequest.Priority.NORMAL),
            needed_by=s.validated_data.get("needed_by"),
            notes=s.validated_data.get("notes", ""),
            apply_moq=s.validated_data.get("apply_moq", False),
            user=request.user,
            request=request,
        )
        return Response(self.get_serializer(pr).data, status=status.HTTP_201_CREATED)


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    serializer_class = PurchaseOrderSerializer
    filterset_class = PurchaseOrderFilter
    search_fields = [
        "po_number",
        "supplier__name",
        "supplier__code",
        "purchase_request__request_number",
        "project__code",
        "project__name",
        "notes",
    ]
    ordering_fields = [
        "po_number",
        "status",
        "total_amount",
        "order_date",
        "expected_delivery_date",
        "created_at",
        "updated_at",
    ]
    ordering = ["-created_at", "-id"]
    required_permissions = {
        "list": "purchase.view",
        "retrieve": "purchase.view",
        "create": "purchase.order",
        "update": "purchase.order",
        "partial_update": "purchase.order",
        "destroy": "purchase.order",
        "approve": "purchase.approve",
        "send": "purchase.order",
        "cancel": "purchase.order",
        "close": "purchase.order",
        "receive": "purchase.receive",
    }

    def get_queryset(self):
        return (
            PurchaseOrder.objects.select_related(
                "supplier",
                "purchase_request",
                "project",
                "bom_revision",
                "default_warehouse",
                "created_by",
                "approved_by",
                "sent_by",
            )
            .prefetch_related("items__component", "items__supplier_part")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        items = data.pop("items", [])
        po = create_purchase_order(data=data, items=items, user=request.user, request=request)
        return Response(self.get_serializer(po).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        items = data.pop("items", None)
        po = update_purchase_order(instance, data=data, items=items, user=request.user, request=request)
        return Response(self.get_serializer(po).data)

    def destroy(self, request, *args, **kwargs):
        po = self.get_object()
        if po.status != PurchaseOrder.Status.DRAFT:
            raise Conflict("Only DRAFT purchase orders can be deleted. Cancel the order instead.")
        if po.goods_receipts.exists():
            raise Conflict("Purchase order has goods receipts and cannot be deleted.")
        po.soft_delete(request.user)
        audit.record_delete(po, request=request, user=request.user, soft=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses={200: PurchaseOrderSerializer})
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        po = approve_purchase_order(self.get_object(), user=request.user, request=request)
        return Response(self.get_serializer(po).data)

    @extend_schema(request=None, responses={200: PurchaseOrderSerializer})
    @action(detail=True, methods=["post"])
    def send(self, request, pk=None):
        po = send_purchase_order(self.get_object(), user=request.user, request=request)
        return Response(self.get_serializer(po).data)

    @extend_schema(request=None, responses={200: PurchaseOrderSerializer})
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        po = cancel_purchase_order(self.get_object(), user=request.user, request=request)
        return Response(self.get_serializer(po).data)

    @extend_schema(request=None, responses={200: PurchaseOrderSerializer})
    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        po = close_purchase_order(self.get_object(), user=request.user, request=request)
        return Response(self.get_serializer(po).data)

    @extend_schema(request=GoodsReceiptSerializer, responses={201: GoodsReceiptSerializer})
    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        po = self.get_object()
        payload = {
            **request.data,
            "purchase_order": po.pk,
            "warehouse": request.data.get("warehouse") or po.default_warehouse_id,
        }
        serializer = GoodsReceiptSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        items = data.pop("items", [])
        post_imm = data.pop("post_immediately", True)
        grn = create_goods_receipt(
            data=data,
            items=items,
            post_immediately=post_imm,
            user=request.user,
            request=request,
        )
        return Response(GoodsReceiptSerializer(grn).data, status=status.HTTP_201_CREATED)


class GoodsReceiptViewSet(viewsets.ModelViewSet):
    serializer_class = GoodsReceiptSerializer
    filterset_class = GoodsReceiptFilter
    search_fields = [
        "receipt_number",
        "purchase_order__po_number",
        "purchase_order__supplier__name",
        "supplier_delivery_note",
        "notes",
    ]
    ordering_fields = ["receipt_number", "status", "received_at", "created_at"]
    ordering = ["-created_at", "-id"]
    http_method_names = ["get", "post", "head", "options"]
    required_permissions = {
        "list": "purchase.view",
        "retrieve": "purchase.view",
        "create": "purchase.receive",
        "post_receipt": "purchase.receive",
    }

    def get_queryset(self):
        return (
            GoodsReceipt.objects.select_related(
                "purchase_order__supplier",
                "warehouse",
                "received_by",
                "created_by",
            )
            .prefetch_related(
                "items__component",
                "items__warehouse",
                "items__location",
            )
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        items = data.pop("items", [])
        post_imm = data.pop("post_immediately", True)
        grn = create_goods_receipt(
            data=data,
            items=items,
            post_immediately=post_imm,
            user=request.user,
            request=request,
        )
        return Response(self.get_serializer(grn).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: GoodsReceiptSerializer})
    @action(detail=True, methods=["post"], url_path="post")
    def post_receipt(self, request, pk=None):
        grn = post_goods_receipt(self.get_object(), user=request.user, request=request)
        return Response(self.get_serializer(grn).data)


class PurchasingSummaryView(APIView):
    required_permissions = {"get": "purchase.view"}

    def get(self, request):
        money_field = DecimalField(max_digits=16, decimal_places=4)
        open_po_statuses = [
            PurchaseOrder.Status.DRAFT,
            PurchaseOrder.Status.APPROVED,
            PurchaseOrder.Status.SENT,
            PurchaseOrder.Status.PARTIALLY_RECEIVED,
        ]
        commitment = PurchaseOrder.objects.filter(status__in=open_po_statuses).aggregate(
            total=Coalesce(Sum(F("total_amount") * F("exchange_rate")), Decimal("0.0000"), output_field=money_field)
        )["total"]
        return Response(
            {
                "open_requests": PurchaseRequest.objects.filter(
                    status__in=[
                        PurchaseRequest.Status.DRAFT,
                        PurchaseRequest.Status.SUBMITTED,
                        PurchaseRequest.Status.APPROVED,
                    ]
                ).count(),
                "pending_approval_requests": PurchaseRequest.objects.filter(
                    status=PurchaseRequest.Status.SUBMITTED
                ).count(),
                "approved_requests": PurchaseRequest.objects.filter(
                    status=PurchaseRequest.Status.APPROVED
                ).count(),
                "open_orders": PurchaseOrder.objects.filter(status__in=open_po_statuses).count(),
                "pending_approval_orders": PurchaseOrder.objects.filter(status=PurchaseOrder.Status.DRAFT).count(),
                "awaiting_delivery_orders": PurchaseOrder.objects.filter(
                    status__in=[
                        PurchaseOrder.Status.APPROVED,
                        PurchaseOrder.Status.SENT,
                        PurchaseOrder.Status.PARTIALLY_RECEIVED,
                    ]
                ).count(),
                "posted_receipts": GoodsReceipt.objects.filter(status=GoodsReceipt.Status.POSTED).count(),
                "open_po_commitment": str(commitment.quantize(Decimal("0.0001"))),
            }
        )


class ComponentPurchaseHistoryView(APIView):
    required_permissions = {"get": "purchase.view"}

    def get(self, request):
        comp_id = request.query_params.get("component")
        if not comp_id:
            raise ValidationError({"component": "Query parameter 'component' is required."})
        component = get_object_or_404(Component, pk=comp_id)

        po_items = (
            PurchaseOrderItem.objects.filter(
                component=component,
                purchase_order__deleted_at__isnull=True,
            )
            .select_related("purchase_order__supplier")
            .order_by("-purchase_order__created_at", "-id")[:25]
        )
        grn_items = (
            GoodsReceiptItem.objects.filter(
                component=component,
                goods_receipt__status=GoodsReceipt.Status.POSTED,
            )
            .select_related("goods_receipt__purchase_order__supplier", "warehouse", "location")
            .order_by("-goods_receipt__received_at", "-id")[:25]
        )

        return Response(
            {
                "component_id": component.id,
                "internal_part_number": component.internal_part_number,
                "purchase_orders": [
                    {
                        "id": poi.id,
                        "purchase_order_id": poi.purchase_order_id,
                        "po_number": poi.purchase_order.po_number,
                        "po_status": poi.purchase_order.status,
                        "supplier_id": poi.purchase_order.supplier_id,
                        "supplier_code": poi.purchase_order.supplier.code,
                        "supplier_name": poi.purchase_order.supplier.name,
                        "supplier_part_number": poi.supplier_part_number_snapshot,
                        "quantity_ordered": str(poi.quantity_ordered),
                        "quantity_received": str(poi.quantity_received),
                        "unit_price": str(poi.unit_price),
                        "line_total": str(poi.line_total),
                        "currency": poi.purchase_order.currency,
                        "order_date": poi.purchase_order.order_date,
                        "created_at": poi.purchase_order.created_at,
                    }
                    for poi in po_items
                ],
                "goods_receipts": [
                    {
                        "id": gi.id,
                        "goods_receipt_id": gi.goods_receipt_id,
                        "receipt_number": gi.goods_receipt.receipt_number,
                        "purchase_order_id": gi.goods_receipt.purchase_order_id,
                        "po_number": gi.goods_receipt.purchase_order.po_number,
                        "supplier_name": gi.goods_receipt.purchase_order.supplier.name,
                        "warehouse_code": gi.warehouse.code,
                        "location_code": gi.location.code if gi.location_id else None,
                        "lot_batch": gi.lot_batch,
                        "quantity_received": str(gi.quantity_received),
                        "unit_cost": str(gi.unit_cost_snapshot),
                        "currency": gi.currency_snapshot,
                        "received_at": gi.goods_receipt.received_at,
                        "stock_transaction_id": gi.stock_transaction_id,
                    }
                    for gi in grn_items
                ],
            }
        )

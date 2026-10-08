"""Inventory REST API. Views validate input and delegate every stock change to ``services``.

Permission codes come from ``apps.accounts.rbac_catalog``; ``HasRBACPermission`` (the global default)
resolves them per action. Anything not mapped is denied.
"""
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.audit.mixins import AuditedModelViewSetMixin
from apps.core.exceptions import Conflict

from . import services
from .filters import InventoryItemFilter, StockReservationFilter, StockTransactionFilter, WarehouseLocationFilter
from .models import InventoryItem, StockReservation, StockTransaction, Warehouse, WarehouseLocation
from .serializers import (
    InventoryItemSerializer,
    StockAdjustmentSerializer,
    StockLevelsSerializer,
    StockMovementSerializer,
    StockReceiptSerializer,
    StockReservationSerializer,
    StockReserveSerializer,
    StockTransactionSerializer,
    StockTransferSerializer,
    WarehouseLocationSerializer,
    WarehouseSerializer,
)

VIEW = "inventory.view"
WAREHOUSE_MANAGE = "inventory.warehouse_manage"
WAREHOUSE_PERMS = {
    "list": VIEW,
    "retrieve": VIEW,
    "create": WAREHOUSE_MANAGE,
    "update": WAREHOUSE_MANAGE,
    "partial_update": WAREHOUSE_MANAGE,
    "destroy": WAREHOUSE_MANAGE,
}


class WarehouseViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """DELETE deactivates (soft-deletes) a warehouse; it is refused while it still holds stock."""

    serializer_class = WarehouseSerializer
    queryset = Warehouse.objects.all()
    filterset_fields = ["is_active"]
    search_fields = ["code", "name", "description"]
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["code"]
    required_permissions = WAREHOUSE_PERMS

    def check_can_delete(self, instance):
        if instance.inventory_items.filter(quantity_on_hand__gt=0).exists():
            raise Conflict("Warehouse still holds stock. Transfer or issue it before deactivating the warehouse.")
        if instance.locations.filter(deleted_at__isnull=True).exists():
            raise Conflict("Warehouse has active locations. Deactivate them first.")


class WarehouseLocationViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """DELETE deactivates (soft-deletes) a location; it is refused while it still holds stock."""

    serializer_class = WarehouseLocationSerializer
    queryset = WarehouseLocation.objects.select_related("warehouse")
    filterset_class = WarehouseLocationFilter
    search_fields = ["code", "name", "warehouse__code"]
    ordering_fields = ["code", "name", "warehouse__code", "created_at"]
    ordering = ["warehouse__code", "code"]
    required_permissions = WAREHOUSE_PERMS

    def check_can_delete(self, instance):
        if instance.inventory_items.filter(quantity_on_hand__gt=0).exists():
            raise Conflict("Location still holds stock. Transfer or issue it before deactivating the location.")
        if instance.sub_locations.filter(deleted_at__isnull=True).exists():
            raise Conflict("Location has active sub-locations.")


class InventoryItemViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Stock balances (read-only). Only thresholds are writable, via ``PATCH /levels``."""

    serializer_class = InventoryItemSerializer
    filterset_class = InventoryItemFilter
    search_fields = ["component__internal_part_number", "component__mpn", "component__name", "lot_batch"]
    ordering_fields = [
        "component__internal_part_number", "warehouse__code", "location__code", "quantity_on_hand",
        "quantity_reserved", "available_qty", "updated_at",
    ]
    ordering = ["component__internal_part_number", "warehouse__code", "location__code"]
    required_permissions = {
        "list": VIEW,
        "retrieve": VIEW,
        "summary": VIEW,
        "levels": "inventory.manage",
    }

    def get_queryset(self):
        return services.annotate_stock_status(
            InventoryItem.objects.select_related("component", "warehouse", "location")
        )

    @extend_schema(request=StockLevelsSerializer, responses=InventoryItemSerializer)
    @action(detail=True, methods=["patch"])
    def levels(self, request, pk=None):
        item = self.get_object()
        ser = StockLevelsSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        services.set_stock_levels(item, request.user, request=request, **ser.validated_data)
        return Response(self.get_serializer(self.get_queryset().get(pk=item.pk)).data)

    @extend_schema(
        parameters=[OpenApiParameter("component", int), OpenApiParameter("warehouse", int)],
        responses={200: dict},
    )
    @action(detail=False, methods=["get"])
    def summary(self, request):
        """Dataset-wide totals (respects the same filters as the list)."""
        qs = InventoryItem.objects.all()
        if c := request.query_params.get("component"):
            qs = qs.filter(component_id=c) if c.isdigit() else qs.none()
        if w := request.query_params.get("warehouse"):
            qs = qs.filter(warehouse_id=w) if w.isdigit() else qs.none()
        return Response(services.stock_summary(qs))


class StockTransactionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Append-only ledger. No create/update/delete endpoints exist."""

    serializer_class = StockTransactionSerializer
    queryset = StockTransaction.objects.select_related("component", "warehouse", "location", "performed_by")
    filterset_class = StockTransactionFilter
    search_fields = ["component__internal_part_number", "component__mpn", "reference", "reason", "lot_batch"]
    ordering_fields = ["timestamp", "quantity", "transaction_type"]
    ordering = ["-timestamp", "-id"]
    required_permissions = {"list": "inventory.transaction_view", "retrieve": "inventory.transaction_view"}


class StockReservationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = StockReservationSerializer
    queryset = StockReservation.objects.select_related(
        "component", "warehouse", "location", "project", "created_by", "released_by"
    )
    filterset_class = StockReservationFilter
    search_fields = ["component__internal_part_number", "component__mpn", "reference_id", "notes"]
    ordering_fields = ["created_at", "quantity", "status"]
    ordering = ["-created_at"]
    required_permissions = {
        "list": VIEW,
        "retrieve": VIEW,
        "release": "inventory.reserve",
        "cancel": "inventory.reserve",
    }

    @extend_schema(request=None, responses=StockReservationSerializer)
    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        self.get_object()  # 404 for unknown ids
        res = services.release_reservation(pk, request.user, request=request)
        return Response(StockReservationSerializer(res).data)

    @extend_schema(request=None, responses=StockReservationSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        self.get_object()
        res = services.cancel_reservation(pk, request.user, request=request)
        return Response(StockReservationSerializer(res).data)


class StockOperationViewSet(viewsets.GenericViewSet):
    """Stock-changing operations. Each returns the created ledger row(s)."""

    required_permissions = {
        "receive": "inventory.receive",
        "issue": "inventory.issue",
        "adjust": "inventory.adjust",
        "transfer": "inventory.transfer",
        "reserve": "inventory.reserve",
    }
    serializer_class = StockMovementSerializer

    def _movement(self, data) -> services.Movement:
        return services.Movement(
            component=data["component"], warehouse=data["warehouse"], location=data.get("location"),
            quantity=data["quantity"], lot_batch=data.get("lot_batch", ""), reason=data.get("reason", ""),
            notes=data.get("notes", ""), reference=data.get("reference", ""),
            unit_cost=data.get("unit_cost"), currency=data.get("currency", ""),
        )

    def _validated(self, serializer_class):
        ser = serializer_class(data=request_data(self.request))
        ser.is_valid(raise_exception=True)
        return ser.validated_data

    @extend_schema(request=StockReceiptSerializer, responses={201: StockTransactionSerializer})
    @action(detail=False, methods=["post"])
    def receive(self, request):
        txn, _ = services.receive_stock(self._movement(self._validated(StockReceiptSerializer)), request.user, request)
        return Response(StockTransactionSerializer(txn).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=StockMovementSerializer, responses={201: StockTransactionSerializer})
    @action(detail=False, methods=["post"])
    def issue(self, request):
        txn, _ = services.issue_stock(self._movement(self._validated(StockMovementSerializer)), request.user, request)
        return Response(StockTransactionSerializer(txn).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=StockAdjustmentSerializer, responses={201: StockTransactionSerializer})
    @action(detail=False, methods=["post"])
    def adjust(self, request):
        data = self._validated(StockAdjustmentSerializer)
        txn, _ = services.adjust_stock(self._movement(data), data["direction"], request.user, request)
        return Response(StockTransactionSerializer(txn).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=StockTransferSerializer, responses={201: StockTransactionSerializer(many=True)})
    @action(detail=False, methods=["post"])
    def transfer(self, request):
        d = self._validated(StockTransferSerializer)
        out_txn, in_txn = services.transfer_stock(
            d["component"], d["from_warehouse"], d.get("from_location"), d["to_warehouse"], d.get("to_location"),
            d["quantity"], request.user, lot_batch=d["lot_batch"], reason=d["reason"], notes=d["notes"],
            reference=d["reference"], request=request,
        )
        return Response(StockTransactionSerializer([out_txn, in_txn], many=True).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=StockReserveSerializer, responses={201: StockReservationSerializer})
    @action(detail=False, methods=["post"])
    def reserve(self, request):
        d = self._validated(StockReserveSerializer)
        res = services.reserve_stock(
            d["component"], d["warehouse"], d.get("location"), d["quantity"], request.user,
            lot_batch=d["lot_batch"], project=d.get("project"), bom_revision=d.get("bom_revision"),
            reference_type=d["reference_type"], reference_id=d["reference_id"], notes=d["notes"], request=request,
        )
        return Response(StockReservationSerializer(res).data, status=status.HTTP_201_CREATED)


def request_data(request):
    """Plain dict copy of the request body (JSON or form). Never mutate ``request.data`` itself."""
    data = request.data
    if hasattr(data, "dict"):
        return data.dict()
    return dict(data)

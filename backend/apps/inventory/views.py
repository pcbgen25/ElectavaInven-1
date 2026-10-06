from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import F
from .models import Warehouse, WarehouseLocation, InventoryItem, StockTransaction, StockReservation
from .serializers import (WarehouseSerializer, WarehouseLocationSerializer, 
    InventoryItemSerializer, StockTransactionSerializer, StockReservationSerializer,
    StockOperationSerializer, StockTransferSerializer)
from .services import execute_stock_operation, transfer_stock, reserve_stock, release_reservation
from apps.core.permissions import HasRBACPermission
from apps.components.models import Component

class WarehouseViewSet(viewsets.ModelViewSet):
    queryset = Warehouse.objects.all()
    serializer_class = WarehouseSerializer
    permission_classes = [HasRBACPermission]
    required_permissions = {
        'list': 'inventory.view',
        'retrieve': 'inventory.view',
        'create': 'inventory.manage',
        'update': 'inventory.manage',
        'partial_update': 'inventory.manage',
        'destroy': 'inventory.manage',
    }

    @action(detail=True, methods=['get'])
    def locations(self, request, pk=None):
        locations = WarehouseLocation.objects.filter(warehouse_id=pk)
        return Response(WarehouseLocationSerializer(locations, many=True).data)

class WarehouseLocationViewSet(viewsets.ModelViewSet):
    queryset = WarehouseLocation.objects.all()
    serializer_class = WarehouseLocationSerializer
    permission_classes = [HasRBACPermission]
    required_permissions = {
        'list': 'inventory.view',
        'retrieve': 'inventory.view',
        'create': 'inventory.manage',
        'update': 'inventory.manage',
        'partial_update': 'inventory.manage',
        'destroy': 'inventory.manage',
    }

class InventoryItemViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InventoryItem.objects.select_related('component', 'warehouse', 'location').all()
    serializer_class = InventoryItemSerializer
    permission_classes = [HasRBACPermission]
    required_permissions = {'list': 'inventory.view', 'retrieve': 'inventory.view', '*': 'inventory.view'}
    filterset_fields = ['component', 'warehouse', 'location']

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        items = self.queryset.filter(quantity_on_hand__lte=F('reorder_level'))
        page = self.paginate_queryset(items)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(self.get_serializer(items, many=True).data)

class StockTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockTransaction.objects.select_related('component', 'warehouse', 'location', 'performed_by').all()
    serializer_class = StockTransactionSerializer
    permission_classes = [HasRBACPermission]
    required_permissions = {'list': 'inventory.transaction_view', 'retrieve': 'inventory.transaction_view', '*': 'inventory.transaction_view'}
    filterset_fields = ['component', 'warehouse', 'transaction_type', 'performed_by']

class StockReservationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = StockReservation.objects.all()
    serializer_class = StockReservationSerializer
    permission_classes = [HasRBACPermission]
    required_permissions = {'list': 'inventory.view', 'retrieve': 'inventory.view', '*': 'inventory.view'}
    filterset_fields = ['component', 'warehouse', 'status']

class StockOperationViewSet(viewsets.ViewSet):
    permission_classes = [HasRBACPermission]
    required_permissions = {}
    
    def _execute_op(self, request, op_type):
        serializer = StockOperationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        component = Component.objects.get(id=data['component_id'])
        warehouse = Warehouse.objects.get(id=data['warehouse_id'])
        location = WarehouseLocation.objects.filter(id=data['location_id']).first() if data.get('location_id') else None
        
        try:
            txn, item = execute_stock_operation(
                op_type,
                component=component,
                warehouse=warehouse,
                location=location,
                quantity=data['quantity'],
                user=request.user,
                reason=data.get('reason', ''),
                notes=data.get('notes', ''),
                reference_type=data.get('reference_type', ''),
                reference_id=data.get('reference_id', ''),
                lot_batch=data.get('lot_batch', '')
            )
            return Response(StockTransactionSerializer(txn).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], required_permissions='inventory.receive')
    def receive(self, request):
        return self._execute_op(request, StockTransaction.TransactionType.RECEIPT)

    @action(detail=False, methods=['post'], required_permissions='inventory.issue')
    def issue(self, request):
        return self._execute_op(request, StockTransaction.TransactionType.ISSUE)

    @action(detail=False, methods=['post'], required_permissions='inventory.adjust')
    def adjust(self, request):
        # Determine if adjust in or out based on quantity payload convention, or explicit field
        qty = float(request.data.get('quantity', 0))
        op_type = StockTransaction.TransactionType.ADJUSTMENT_IN if qty > 0 else StockTransaction.TransactionType.ADJUSTMENT_OUT
        request.data['quantity'] = abs(qty)
        return self._execute_op(request, op_type)

    @action(detail=False, methods=['post'], required_permissions='inventory.transfer')
    def transfer(self, request):
        serializer = StockTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        component = Component.objects.get(id=data['component_id'])
        from_warehouse = Warehouse.objects.get(id=data['from_warehouse_id'])
        from_location = WarehouseLocation.objects.filter(id=data['from_location_id']).first() if data.get('from_location_id') else None
        to_warehouse = Warehouse.objects.get(id=data['to_warehouse_id'])
        to_location = WarehouseLocation.objects.filter(id=data['to_location_id']).first() if data.get('to_location_id') else None
        
        try:
            out_txn, in_txn = transfer_stock(
                component, from_warehouse, from_location, to_warehouse, to_location,
                quantity=data['quantity'], user=request.user, reason=data.get('reason', ''), lot_batch=data.get('lot_batch', '')
            )
            return Response({"detail": "Transfer successful"}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], required_permissions='inventory.reserve')
    def reserve(self, request):
        serializer = StockOperationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        
        component = Component.objects.get(id=data['component_id'])
        warehouse = Warehouse.objects.get(id=data['warehouse_id'])
        location = WarehouseLocation.objects.filter(id=data['location_id']).first() if data.get('location_id') else None
        
        try:
            res = reserve_stock(
                component, warehouse, location, data['quantity'], request.user,
                reference_type=data.get('reference_type', ''), reference_id=data.get('reference_id', ''),
                lot_batch=data.get('lot_batch', '')
            )
            return Response(StockReservationSerializer(res).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], required_permissions='inventory.reserve')
    def release_reservation(self, request, pk=None):
        try:
            res = release_reservation(pk, request.user)
            return Response(StockReservationSerializer(res).data)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

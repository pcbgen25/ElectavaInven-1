from rest_framework import serializers
from .models import Warehouse, WarehouseLocation, InventoryItem, StockTransaction, StockReservation
from apps.components.serializers import ComponentListSerializer

class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = '__all__'

class WarehouseLocationSerializer(serializers.ModelSerializer):
    warehouse_code = serializers.CharField(source='warehouse.code', read_only=True)
    class Meta:
        model = WarehouseLocation
        fields = '__all__'

class InventoryItemSerializer(serializers.ModelSerializer):
    component_mpn = serializers.CharField(source='component.mpn', read_only=True)
    warehouse_code = serializers.CharField(source='warehouse.code', read_only=True)
    location_code = serializers.CharField(source='location.code', read_only=True)
    quantity_available = serializers.DecimalField(max_digits=12, decimal_places=4, read_only=True)
    
    class Meta:
        model = InventoryItem
        fields = '__all__'

class StockTransactionSerializer(serializers.ModelSerializer):
    component_mpn = serializers.CharField(source='component.mpn', read_only=True)
    warehouse_code = serializers.CharField(source='warehouse.code', read_only=True)
    location_code = serializers.CharField(source='location.code', read_only=True)
    performed_by_name = serializers.CharField(source='performed_by.username', read_only=True)

    class Meta:
        model = StockTransaction
        fields = '__all__'

class StockReservationSerializer(serializers.ModelSerializer):
    component_mpn = serializers.CharField(source='component.mpn', read_only=True)
    class Meta:
        model = StockReservation
        fields = '__all__'

class StockOperationSerializer(serializers.Serializer):
    component_id = serializers.IntegerField()
    warehouse_id = serializers.IntegerField()
    location_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=4)
    reason = serializers.CharField(max_length=100, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    reference_type = serializers.CharField(max_length=50, required=False, allow_blank=True)
    reference_id = serializers.CharField(max_length=50, required=False, allow_blank=True)
    lot_batch = serializers.CharField(max_length=100, required=False, allow_blank=True)

class StockTransferSerializer(serializers.Serializer):
    component_id = serializers.IntegerField()
    from_warehouse_id = serializers.IntegerField()
    from_location_id = serializers.IntegerField(required=False, allow_null=True)
    to_warehouse_id = serializers.IntegerField()
    to_location_id = serializers.IntegerField(required=False, allow_null=True)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=4)
    reason = serializers.CharField(max_length=100, required=False, allow_blank=True)
    lot_batch = serializers.CharField(max_length=100, required=False, allow_blank=True)

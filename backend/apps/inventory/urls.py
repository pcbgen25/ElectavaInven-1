from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (WarehouseViewSet, WarehouseLocationViewSet, InventoryItemViewSet, 
                    StockTransactionViewSet, StockReservationViewSet, StockOperationViewSet)

router = DefaultRouter()
router.register(r'warehouses', WarehouseViewSet, basename='warehouse')
router.register(r'locations', WarehouseLocationViewSet, basename='location')
router.register(r'stock', InventoryItemViewSet, basename='stock')
router.register(r'transactions', StockTransactionViewSet, basename='transaction')
router.register(r'reservations', StockReservationViewSet, basename='reservation')
router.register(r'operations', StockOperationViewSet, basename='operation')

urlpatterns = [
    path('', include(router.urls)),
]

from apps.core.routers import OptionalSlashRouter

from .views import (
    InventoryItemViewSet,
    StockOperationViewSet,
    StockReservationViewSet,
    StockTransactionViewSet,
    WarehouseLocationViewSet,
    WarehouseViewSet,
)

# Mounted at /api/inventory/. Same router as Phase 1: trailing slash optional.
router = OptionalSlashRouter()
router.register("warehouses", WarehouseViewSet, basename="warehouse")
router.register("locations", WarehouseLocationViewSet, basename="location")
router.register("stock", InventoryItemViewSet, basename="stock")
router.register("transactions", StockTransactionViewSet, basename="transaction")
router.register("reservations", StockReservationViewSet, basename="reservation")
router.register("operations", StockOperationViewSet, basename="operation")

urlpatterns = router.urls

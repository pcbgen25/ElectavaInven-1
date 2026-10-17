from django.urls import path

from apps.core.routers import OptionalSlashRouter

from .views import (
    ComponentPurchaseHistoryView,
    GoodsReceiptViewSet,
    PurchaseOrderViewSet,
    PurchaseRequestViewSet,
    PurchasingSummaryView,
)

router = OptionalSlashRouter()
router.register("requests", PurchaseRequestViewSet, basename="purchase-request")
router.register("orders", PurchaseOrderViewSet, basename="purchase-order")
router.register("goods-receipts", GoodsReceiptViewSet, basename="goods-receipt")

urlpatterns = [
    path("summary", PurchasingSummaryView.as_view(), name="purchasing-summary"),
    path("summary/", PurchasingSummaryView.as_view()),
    path("component-history", ComponentPurchaseHistoryView.as_view(), name="purchasing-component-history"),
    path("component-history/", ComponentPurchaseHistoryView.as_view()),
    *router.urls,
]

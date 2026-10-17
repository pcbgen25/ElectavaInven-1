from apps.core.routers import OptionalSlashRouter

from .views import SupplierContactViewSet, SupplierPartViewSet, SupplierViewSet

router = OptionalSlashRouter()
router.register("suppliers", SupplierViewSet, basename="supplier")
router.register("supplier-contacts", SupplierContactViewSet, basename="supplier-contact")
router.register("supplier-parts", SupplierPartViewSet, basename="supplier-part")

urlpatterns = router.urls

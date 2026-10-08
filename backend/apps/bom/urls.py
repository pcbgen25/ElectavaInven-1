from apps.core.routers import OptionalSlashRouter

from .views import BOMItemViewSet, BOMRevisionViewSet, BOMViewSet

# Same router as Phase 1: trailing slash optional, no browsable API root.
router = OptionalSlashRouter()
router.register("boms", BOMViewSet, basename="bom")
router.register("bom-revisions", BOMRevisionViewSet, basename="bomrevision")
router.register("bom-items", BOMItemViewSet, basename="bomitem")

urlpatterns = router.urls

from rest_framework.routers import DefaultRouter
from .views import BOMViewSet, BOMRevisionViewSet, BOMItemViewSet

router = DefaultRouter()
router.register(r'boms', BOMViewSet, basename='bom')
router.register(r'bom-revisions', BOMRevisionViewSet, basename='bomrevision')
router.register(r'bom-items', BOMItemViewSet, basename='bomitem')

urlpatterns = router.urls

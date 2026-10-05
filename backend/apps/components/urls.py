from apps.core.routers import OptionalSlashRouter

from .views import CategoryViewSet, ComponentViewSet, PackageViewSet, SpecificationDefinitionViewSet

router = OptionalSlashRouter()
router.register("components", ComponentViewSet, basename="component")
router.register("categories", CategoryViewSet, basename="category")
router.register("packages", PackageViewSet, basename="package")
router.register("specification-definitions", SpecificationDefinitionViewSet, basename="specification-definition")

urlpatterns = router.urls

from apps.core.routers import OptionalSlashRouter

from .views import ProjectViewSet

router = OptionalSlashRouter()
router.register("projects", ProjectViewSet, basename="project")

urlpatterns = router.urls

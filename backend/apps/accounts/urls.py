from apps.core.routers import OptionalSlashRouter

from .views import PermissionViewSet, RoleViewSet, UserViewSet

router = OptionalSlashRouter()
router.register("users", UserViewSet, basename="user")
router.register("roles", RoleViewSet, basename="role")
router.register("permissions", PermissionViewSet, basename="permission")

urlpatterns = router.urls

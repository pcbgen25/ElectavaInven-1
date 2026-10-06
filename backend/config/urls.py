"""Root URL configuration. All API routes live under /api/."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api_patterns = [
    path("auth/", include("apps.accounts.urls_auth")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.audit.urls")),
    path("", include("apps.manufacturers.urls")),
    path("", include("apps.projects.urls")),
    path("", include("apps.bom.urls")),
    path("", include("apps.components.urls")),
    path("", include("apps.reports.urls")),
    path("schema", SpectacularAPIView.as_view(), name="schema"),
    path("docs", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("api/", include(api_patterns)),
]

if settings.DEBUG and not settings.USE_S3:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

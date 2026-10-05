from django.urls import path
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import AUTHENTICATED

from .services import dashboard_summary


class DashboardView(APIView):
    """Content is filtered by the caller's permissions inside the service."""

    required_permissions = {"get": AUTHENTICATED}

    @extend_schema(responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response(dashboard_summary(request.user))


urlpatterns = [path("dashboard", DashboardView.as_view(), name="dashboard")]

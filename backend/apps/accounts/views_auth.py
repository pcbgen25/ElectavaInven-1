"""Session-based authentication endpoints (same-origin via the Next.js proxy)."""
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.audit import services as audit
from apps.audit.models import AuditAction
from apps.core.permissions import AUTHENTICATED

from .serializers import ChangePasswordSerializer, LoginSerializer, MeSerializer


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Sets the ``csrftoken`` cookie. Call once before login."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(responses={200: None})
    def get(self, request):
        return Response({"detail": "CSRF cookie set."})


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(request=LoginSerializer, responses={200: MeSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].strip().lower()
        user = authenticate(request, email=email, password=serializer.validated_data["password"])
        if user is None:
            # Same message for unknown user / wrong password / inactive (no account enumeration).
            return Response({"detail": "Invalid email or password."}, status=status.HTTP_400_BAD_REQUEST)
        login(request, user)
        return Response(MeSerializer(user).data)


class LogoutView(APIView):
    required_permissions = {"post": AUTHENTICATED}

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    required_permissions = {"get": AUTHENTICATED}

    @extend_schema(responses={200: MeSerializer})
    def get(self, request):
        return Response(MeSerializer(request.user).data)


class ChangePasswordView(APIView):
    required_permissions = {"post": AUTHENTICATED}
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @extend_schema(request=ChangePasswordSerializer, responses={204: None})
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        update_session_auth_hash(request, user)  # keep this session, invalidate others
        audit.record(
            AuditAction.PASSWORD_CHANGE, entity_type="accounts.user", entity_id=user.pk,
            entity_repr=str(user), request=request,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

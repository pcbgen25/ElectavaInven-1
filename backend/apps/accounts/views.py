from django.db.models import Count
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.audit import services as audit
from apps.core.exceptions import Conflict

from . import services
from .models import Permission, Role, User
from .serializers import (
    PermissionSerializer,
    RolePermissionsSerializer,
    RoleSerializer,
    SetPasswordSerializer,
    UserSerializer,
)


class UserViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
    mixins.UpdateModelMixin, viewsets.GenericViewSet,
):
    """Users are never hard-deleted; deactivate with ``is_active=false``."""

    queryset = User.objects.prefetch_related("roles").all()
    serializer_class = UserSerializer
    filterset_fields = ["is_active", "roles__code", "department"]
    search_fields = ["email", "first_name", "last_name", "job_title", "department"]
    ordering_fields = ["email", "first_name", "last_name", "last_login", "date_joined"]
    required_permissions = {"*": "user.manage"}

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        roles = data.pop("role_codes", [])
        password = data.pop("password")
        serializer.instance = services.create_user(
            actor=self.request.user, request=self.request, data=data, roles=roles, password=password
        )

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        roles = data.pop("role_codes", None)
        serializer.instance = services.update_user(
            actor=self.request.user, request=self.request, user=serializer.instance, data=data, roles=roles
        )

    @extend_schema(request=SetPasswordSerializer, responses={204: None})
    @action(detail=True, methods=["post"], url_path="set-password")
    def set_password(self, request, pk=None):
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.set_password(
            actor=request.user, request=request, user=self.get_object(), password=serializer.validated_data["password"]
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.prefetch_related("permissions").annotate(user_count=Count("users", distinct=True))
    serializer_class = RoleSerializer
    search_fields = ["code", "name"]
    ordering_fields = ["code", "name"]
    required_permissions = {
        "list": ["role.manage", "user.manage"],
        "retrieve": ["role.manage", "user.manage"],
        "create": "role.manage",
        "update": "role.manage",
        "partial_update": "role.manage",
        "destroy": "role.manage",
        "set_permissions": "role.manage",
    }

    def perform_create(self, serializer):
        role = serializer.save(is_system=False)
        audit.record_create(role, request=self.request)

    def perform_update(self, serializer):
        old = audit.snapshot(serializer.instance)
        role = serializer.save()
        audit.record_update(role, old, request=self.request)

    def perform_destroy(self, instance):
        if instance.is_system:
            raise ValidationError({"detail": "System roles cannot be deleted."})
        if instance.users.exists():
            raise Conflict("Role is assigned to users. Remove it from all users first.")
        audit.record_delete(instance, request=self.request, soft=False)
        instance.delete()

    @extend_schema(request=RolePermissionsSerializer, responses={200: RoleSerializer})
    @action(detail=True, methods=["put"], url_path="permissions")
    def set_permissions(self, request, pk=None):
        serializer = RolePermissionsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = services.set_role_permissions(
            actor=request.user, request=request, role=self.get_object(),
            codes=serializer.validated_data["permission_codes"],
        )
        return Response(RoleSerializer(self.get_queryset().get(pk=role.pk)).data)


class PermissionViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    pagination_class = None
    filterset_fields = ["module"]
    required_permissions = {"list": ["role.manage", "user.manage"]}

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Permission, Role, User


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ["id", "code", "name", "module"]


class RoleSerializer(serializers.ModelSerializer):
    permission_codes = serializers.SerializerMethodField()
    user_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Role
        fields = ["id", "code", "name", "description", "is_system", "permission_codes", "user_count"]
        read_only_fields = ["is_system"]

    def get_permission_codes(self, obj) -> list[str]:
        return sorted(p.code for p in obj.permissions.all())

    def validate_code(self, value: str) -> str:
        value = value.strip().upper()
        if not value.replace("_", "").isalnum():
            raise serializers.ValidationError("Use letters, digits and underscores only.")
        if self.instance and self.instance.is_system and value != self.instance.code:
            raise serializers.ValidationError("System role codes cannot be changed.")
        return value


class RolePermissionsSerializer(serializers.Serializer):
    permission_codes = serializers.ListField(child=serializers.CharField(max_length=64), allow_empty=True)


class RoleBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "code", "name"]


class UserSerializer(serializers.ModelSerializer):
    roles = RoleBriefSerializer(many=True, read_only=True)
    role_codes = serializers.ListField(
        child=serializers.CharField(), write_only=True, required=False, help_text="Replace the user's roles."
    )
    password = serializers.CharField(
        write_only=True, required=False, allow_blank=False, style={"input_type": "password"},
        help_text="Required on create.",
    )
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "full_name", "job_title", "department", "phone",
            "is_active", "roles", "role_codes", "password", "last_login", "date_joined",
        ]
        read_only_fields = ["last_login", "date_joined"]

    def validate_email(self, value: str) -> str:
        value = value.strip().lower()
        qs = User.objects.filter(email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_role_codes(self, codes: list[str]) -> list[Role]:
        codes = sorted({c.strip().upper() for c in codes})
        roles = list(Role.objects.filter(code__in=codes))
        unknown = set(codes) - {r.code for r in roles}
        if unknown:
            raise serializers.ValidationError(f"Unknown role(s): {', '.join(sorted(unknown))}")
        return roles

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": ["A password is required for new users."]})
        if self.instance is not None and "password" in attrs:
            raise serializers.ValidationError({"password": ["Use the set-password action to change passwords."]})
        return attrs


class SetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": ["Current password is incorrect."]})
        validate_password(attrs["new_password"], user)
        return attrs


class MeSerializer(serializers.ModelSerializer):
    roles = RoleBriefSerializer(many=True, read_only=True)
    permissions = serializers.SerializerMethodField()
    full_name = serializers.CharField(read_only=True)
    is_super_admin = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "full_name", "job_title", "department",
            "roles", "permissions", "is_super_admin", "last_login",
        ]

    def get_permissions(self, obj) -> list[str]:
        return sorted(obj.get_rbac_permissions())

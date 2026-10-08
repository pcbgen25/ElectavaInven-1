from rest_framework import serializers

from apps.accounts.models import User

from .models import Project, ProjectMember


class UserBriefSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "full_name"]


class ProjectMemberSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(is_active=True))
    user_details = UserBriefSerializer(source="user", read_only=True)

    class Meta:
        model = ProjectMember
        fields = ["id", "project", "user", "user_details", "notes", "created_at"]
        read_only_fields = ["project", "created_at"]

    def validate_user(self, user):
        project = self.context.get("project")
        if project is not None and ProjectMember.objects.filter(project=project, user=user).exists():
            raise serializers.ValidationError("This user is already a member of the project.")
        return user


class ProjectSerializer(serializers.ModelSerializer):
    members = ProjectMemberSerializer(many=True, read_only=True)
    created_by = UserBriefSerializer(read_only=True)
    bom_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Project
        fields = [
            "id", "code", "name", "description", "customer", "status", "start_date", "target_date",
            "created_by", "created_at", "updated_at", "members", "bom_count",
        ]
        read_only_fields = ["created_by", "created_at", "updated_at"]

    def validate_code(self, value):
        value = value.strip()
        qs = Project.all_objects.filter(code__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A project with this code already exists.")
        return value

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        target = attrs.get("target_date", getattr(self.instance, "target_date", None))
        if start and target and target < start:
            raise serializers.ValidationError({"target_date": "Target date cannot be before the start date."})
        return attrs

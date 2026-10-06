from rest_framework import serializers
from .models import Project, ProjectMember
from apps.accounts.serializers import UserSerializer

class ProjectMemberSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source="user", read_only=True)
    
    class Meta:
        model = ProjectMember
        fields = ["id", "project", "user", "user_details", "notes", "created_at"]
        read_only_fields = ["project"]

class ProjectSerializer(serializers.ModelSerializer):
    members = ProjectMemberSerializer(many=True, read_only=True)
    
    class Meta:
        model = Project
        fields = ["id", "code", "name", "description", "customer", "status", "start_date", "target_date", "created_by", "created_at", "updated_at", "members"]
        read_only_fields = ["created_by"]

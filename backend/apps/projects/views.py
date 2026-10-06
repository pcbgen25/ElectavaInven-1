from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.core.permissions import HasRBACPermission
from .models import Project, ProjectMember
from .serializers import ProjectSerializer, ProjectMemberSerializer

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all().prefetch_related("members__user")
    serializer_class = ProjectSerializer
    permission_classes = [HasRBACPermission]
    required_permissions = {
        "list": "project.view",
        "retrieve": "project.view",
        "create": "project.create",
        "update": "project.edit",
        "partial_update": "project.edit",
        "destroy": "project.delete"
    }

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], required_permissions="project.manage_members")
    def members(self, request, pk=None):
        project = self.get_object()
        serializer = ProjectMemberSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(project=project)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=["delete"], url_path=r'members/(?P<member_id>\d+)', required_permissions="project.manage_members")
    def remove_member(self, request, pk=None, member_id=None):
        project = self.get_object()
        try:
            member = ProjectMember.objects.get(pk=member_id, project=project)
            member.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProjectMember.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.audit import services as audit
from apps.audit.mixins import AuditedModelViewSetMixin

from .models import Project, ProjectMember
from .serializers import ProjectMemberSerializer, ProjectSerializer, UserBriefSerializer


class ProjectViewSet(AuditedModelViewSetMixin, viewsets.ModelViewSet):
    """DELETE soft-deletes a project; its BOMs and released revisions are preserved (FK PROTECT)."""

    serializer_class = ProjectSerializer
    filterset_fields = ["status"]
    search_fields = ["code", "name", "customer", "description"]
    ordering_fields = ["code", "name", "status", "start_date", "target_date", "created_at", "updated_at"]
    ordering = ["-created_at"]
    required_permissions = {
        "list": "project.view",
        "retrieve": "project.view",
        "create": "project.create",
        "update": "project.edit",
        "partial_update": "project.edit",
        "destroy": "project.delete",
        "members": "project.manage_members",
        "remove_member": "project.manage_members",
        "member_candidates": "project.manage_members",
    }

    def get_queryset(self):
        return (
            Project.objects.select_related("created_by")
            .prefetch_related("members__user")
            .annotate(bom_count=Count("boms", filter=Q(boms__deleted_at__isnull=True), distinct=True))
        )

    @extend_schema(request=ProjectMemberSerializer, responses={201: ProjectMemberSerializer})
    @action(detail=True, methods=["post"])
    def members(self, request, pk=None):
        project = self.get_object()
        serializer = ProjectMemberSerializer(data=request.data, context={"project": project})
        serializer.is_valid(raise_exception=True)
        member = serializer.save(project=project)
        audit.record_create(member, request=request)
        return Response(ProjectMemberSerializer(member).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["delete"], url_path=r"members/(?P<member_id>\d+)")
    def remove_member(self, request, pk=None, member_id=None):
        project = self.get_object()
        member = get_object_or_404(ProjectMember, pk=member_id, project=project)
        audit.record_delete(member, request=request, soft=False)
        member.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses=UserBriefSerializer(many=True))
    @action(detail=True, methods=["get"], url_path="member-candidates")
    def member_candidates(self, request, pk=None):
        """Active users not yet in the project (max 20), filtered by ?search=."""
        project = self.get_object()
        qs = User.objects.filter(is_active=True).exclude(project_memberships__project=project)
        if term := request.query_params.get("search", "").strip():
            qs = qs.filter(Q(email__icontains=term) | Q(first_name__icontains=term) | Q(last_name__icontains=term))
        return Response(UserBriefSerializer(qs.order_by("email")[:20], many=True).data)

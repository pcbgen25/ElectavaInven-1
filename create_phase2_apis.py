import os

# apps/projects/serializers.py
with open('backend/apps/projects/serializers.py', 'w') as f:
    f.write('''from rest_framework import serializers
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
''')

# apps/projects/views.py
with open('backend/apps/projects/views.py', 'w') as f:
    f.write('''from rest_framework import viewsets, status
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
        "GET": "project.view",
        "POST": "project.create",
        "PUT": "project.edit",
        "PATCH": "project.edit",
        "DELETE": "project.delete"
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
''')

# apps/projects/urls.py
with open('backend/apps/projects/urls.py', 'w') as f:
    f.write('''from rest_framework.routers import DefaultRouter
from .views import ProjectViewSet

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')

urlpatterns = router.urls
''')

# apps/bom/serializers.py
with open('backend/apps/bom/serializers.py', 'w') as f:
    f.write('''from rest_framework import serializers
from .models import BOM, BOMRevision, BOMItem
from apps.components.serializers import ComponentListSerializer

class BOMItemSerializer(serializers.ModelSerializer):
    component_details = ComponentListSerializer(source="component", read_only=True)
    
    class Meta:
        model = BOMItem
        fields = ["id", "revision", "component", "component_details", "designators", "quantity", "description", "notes", "unit_cost_snapshot", "total_cost_snapshot"]
        read_only_fields = ["revision"]

class BOMRevisionSerializer(serializers.ModelSerializer):
    items = BOMItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = BOMRevision
        fields = ["id", "bom", "revision_number", "revision_name", "description", "status", "created_by", "created_at", "released_by", "released_at", "items"]
        read_only_fields = ["bom", "created_by", "released_by", "released_at"]

class BOMSerializer(serializers.ModelSerializer):
    revisions = BOMRevisionSerializer(many=True, read_only=True)
    
    class Meta:
        model = BOM
        fields = ["id", "project", "name", "description", "status", "created_by", "created_at", "updated_at", "revisions"]
        read_only_fields = ["created_by"]
''')

# apps/bom/views.py
with open('backend/apps/bom/views.py', 'w') as f:
    f.write('''from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from apps.core.permissions import HasRBACPermission
from .models import BOM, BOMRevision, BOMItem
from .serializers import BOMSerializer, BOMRevisionSerializer, BOMItemSerializer

class BOMViewSet(viewsets.ModelViewSet):
    queryset = BOM.objects.all().prefetch_related("revisions")
    serializer_class = BOMSerializer
    permission_classes = [HasRBACPermission]
    required_permissions = {
        "GET": "bom.view",
        "POST": "bom.create",
        "PUT": "bom.edit",
        "PATCH": "bom.edit",
        "DELETE": "bom.delete"
    }

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class BOMRevisionViewSet(viewsets.ModelViewSet):
    queryset = BOMRevision.objects.all().prefetch_related("items__component")
    serializer_class = BOMRevisionSerializer
    permission_classes = [HasRBACPermission]
    required_permissions = {
        "GET": "bom.view",
        "POST": "bom.create",
        "PUT": "bom.edit",
        "PATCH": "bom.edit",
        "DELETE": "bom.delete"
    }

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"], required_permissions="bom.release")
    def release(self, request, pk=None):
        revision = self.get_object()
        if revision.status == BOMRevision.Status.RELEASED:
            return Response({"detail": "Already released"}, status=status.HTTP_400_BAD_REQUEST)
        
        revision.status = BOMRevision.Status.RELEASED
        revision.released_by = request.user
        revision.released_at = timezone.now()
        
        # Snap cost calculations here or assume already snapped
        revision.save()
        return Response(self.get_serializer(revision).data)

class BOMItemViewSet(viewsets.ModelViewSet):
    queryset = BOMItem.objects.all().select_related("component")
    serializer_class = BOMItemSerializer
    permission_classes = [HasRBACPermission]
    required_permissions = {
        "GET": "bom.view",
        "POST": "bom.edit",
        "PUT": "bom.edit",
        "PATCH": "bom.edit",
        "DELETE": "bom.edit"
    }
''')

# apps/bom/urls.py
with open('backend/apps/bom/urls.py', 'w') as f:
    f.write('''from rest_framework.routers import DefaultRouter
from .views import BOMViewSet, BOMRevisionViewSet, BOMItemViewSet

router = DefaultRouter()
router.register(r'boms', BOMViewSet, basename='bom')
router.register(r'bom-revisions', BOMRevisionViewSet, basename='bomrevision')
router.register(r'bom-items', BOMItemViewSet, basename='bomitem')

urlpatterns = router.urls
''')

print("Created Phase 2 APIs.")

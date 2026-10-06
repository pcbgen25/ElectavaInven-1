from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from apps.core.permissions import HasRBACPermission
from .models import BOM, BOMRevision, BOMItem
from .serializers import BOMSerializer, BOMRevisionSerializer, BOMItemSerializer

class BOMViewSet(viewsets.ModelViewSet):
    @action(detail=False, methods=['post'], required_permissions='bom.import')
    def import_kicad(self, request):
        from .services import parse_kicad_csv, preview_bom_import, create_bom_from_import
        from apps.projects.models import Project
        
        file_obj = request.FILES.get('file')
        if not file_obj:
            return Response({'error': 'No file uploaded'}, status=status.HTTP_400_BAD_REQUEST)
            
        file_content = file_obj.read().decode('utf-8')
        raw_items = parse_kicad_csv(file_content)
        preview = preview_bom_import(raw_items)
        
        return Response({'preview': preview})

    @action(detail=False, methods=['post'], required_permissions='bom.import')
    def confirm_import(self, request):
        from .services import create_bom_from_import
        from apps.projects.models import Project
        
        project_id = request.data.get('project_id')
        name = request.data.get('name')
        matched_items = request.data.get('matched_items', [])
        
        project = Project.objects.get(pk=project_id)
        bom = create_bom_from_import(project, name, request.user, matched_items)
        
        return Response(BOMSerializer(bom).data, status=status.HTTP_201_CREATED)

    queryset = BOM.objects.all().prefetch_related("revisions")
    serializer_class = BOMSerializer
    permission_classes = [HasRBACPermission]
    required_permissions = {
        "list": "bom.view",
        "retrieve": "bom.view",
        "create": "bom.create",
        "update": "bom.edit",
        "partial_update": "bom.edit",
        "destroy": "bom.delete"
    }

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class BOMRevisionViewSet(viewsets.ModelViewSet):
    @action(detail=False, methods=['get'], required_permissions='bom.compare')
    def compare(self, request):
        from .services import compare_revisions
        rev_a_id = request.query_params.get('rev_a')
        rev_b_id = request.query_params.get('rev_b')
        
        if not rev_a_id or not rev_b_id:
            return Response({'error': 'rev_a and rev_b required'}, status=400)
            
        rev_a = BOMRevision.objects.get(pk=rev_a_id)
        rev_b = BOMRevision.objects.get(pk=rev_b_id)
        diffs = compare_revisions(rev_a, rev_b)
        
        return Response({'diff': diffs})

    queryset = BOMRevision.objects.all().prefetch_related("items__component")
    serializer_class = BOMRevisionSerializer
    permission_classes = [HasRBACPermission]
    required_permissions = {
        "list": "bom.view",
        "retrieve": "bom.view",
        "create": "bom.create",
        "update": "bom.edit",
        "partial_update": "bom.edit",
        "destroy": "bom.delete"
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
        "list": "bom.view",
        "retrieve": "bom.view",
        "create": "bom.edit",
        "update": "bom.edit",
        "partial_update": "bom.edit",
        "DELETE": "bom.edit"
    }

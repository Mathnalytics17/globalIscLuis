from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from permissions import ActionPermissionMixin, HasSecurityPermission
from apps.users.api.models.index import User
from apps.activesTree.api.serializers.activesTree.index import RecursiveFolderSerializer
from apps.activesTree.api.models.index import Carpeta
from collections import defaultdict

from rest_framework.decorators import action
class ActivesTreeViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    """
    API para estructura básica de carpetas
    """
    queryset = Carpeta.objects.select_related('compania', 'machine', 'muestra')
    permission_classes = [IsAuthenticated, HasSecurityPermission]
    permission_action_map = {
        "basic_structure": "activos.ver",
        "list": "activos.ver",
        "retrieve": "activos.ver",
    }

    @action(detail=False, methods=['get'])
    def basic_structure(self, request):
        """
        Retorna solo la estructura jerárquica básica de carpetas
        """
        try:
            # Obtener solo carpetas raíz y precargar toda la jerarquía
            queryset = Carpeta.objects.select_related('compania', 'machine', 'muestra').prefetch_related(
                'machine__puntos_muestreo',
            )
            user = request.user
            if not (user.is_superuser or user.role == User.Role.GLOBAL):
                queryset = queryset.filter(compania=user.empresa)
            folders = list(queryset.order_by('id'))
            children_by_parent = defaultdict(list)
            for folder in folders:
                children_by_parent[folder.id_parent_node].append(folder)

            serializer = RecursiveFolderSerializer(
                children_by_parent['-1'],
                many=True,
                context={'children_by_parent': children_by_parent},
            )
            
            return Response({
                "success": True,
                "structure": serializer.data
            })
            
        except Exception as e:
            return Response({
                "success": False,
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

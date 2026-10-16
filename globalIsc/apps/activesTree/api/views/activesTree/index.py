from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from permissions import ActionPermissionMixin, HasSecurityPermission
from apps.users.api.models.index import User
from apps.activesTree.api.serializers.activesTree.index import RecursiveFolderSerializer
from apps.activesTree.api.models.index import Carpeta
from apps.activesTree.services import ensure_active_company_roots
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
            # La raíz se mantiene por señales y se reconcilia aquí para las
            # empresas que existían antes de activar esa regla.
            ensure_active_company_roots()
            # Obtener solo carpetas raíz y precargar toda la jerarquía
            queryset = Carpeta.objects.select_related('compania', 'machine', 'muestra').prefetch_related(
                'machine__puntos_muestreo__lubricante_catalogo',
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
            
        except Exception:
            logger.exception("No se pudo consultar la estructura de carpetas")
            return Response({
                "success": False,
                "error": "No se pudo consultar la estructura de carpetas."
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

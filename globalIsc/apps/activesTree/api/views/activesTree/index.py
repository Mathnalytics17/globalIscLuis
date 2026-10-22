import logging

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from permissions import ActionPermissionMixin, HasSecurityPermission
from apps.users.api.models.index import User
from apps.users.api.data_scope import scope_queryset
from apps.activesTree.api.serializers.activesTree.index import RecursiveFolderSerializer
from apps.activesTree.api.models.index import Carpeta
from apps.activesTree.services import ensure_active_company_roots, _preferred_machine_node
from collections import defaultdict

from rest_framework.decorators import action


logger = logging.getLogger(__name__)


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
            ).filter(Q(machine__isnull=True) | Q(machine__activo=True))
            user = request.user
            queryset = scope_queryset(queryset, user, "compania_id")
            folders = list(queryset.order_by('id'))
            # Old imports could leave two visual nodes pointing to the same
            # machine.  Do not render a duplicate while the data is awaiting
            # the permanent reconciliation migration/command.
            root_ids = {
                folder.compania_id: folder.id
                for folder in folders
                if folder.typeFolder == 'root' and str(folder.id_parent_node) == '-1'
            }
            machine_nodes = defaultdict(list)
            for folder in folders:
                if folder.machine_id:
                    machine_nodes[folder.machine_id].append(folder)
            duplicate_node_ids = set()
            for nodes in machine_nodes.values():
                if len(nodes) > 1:
                    root_id = root_ids.get(nodes[0].compania_id)
                    keep = _preferred_machine_node(nodes, root_id)
                    duplicate_node_ids.update(node.id for node in nodes if node.id != keep.id)
            if duplicate_node_ids:
                folders = [folder for folder in folders if folder.id not in duplicate_node_ids]
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

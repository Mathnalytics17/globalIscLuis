from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from apps.activesTree.api.serializers.index import ActiveTreesSerializer
from apps.activesTree.api.serializers.activesTree.index import RecursiveFolderSerializer
from apps.activesTree.api.models.index import Carpeta
from rest_framework.decorators import action
class ActivesTreeViewSet(viewsets.ModelViewSet):
    """
    API para estructura básica de carpetas
    """
    queryset = Carpeta.objects.all()
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'])
    def basic_structure(self, request):
        """
        Retorna solo la estructura jerárquica básica de carpetas
        """
        try:
            # Obtener solo carpetas raíz y precargar toda la jerarquía
            root_folders = Carpeta.objects.filter(id_parent_node='-1')
            
            serializer = RecursiveFolderSerializer(root_folders, many=True)
            
            return Response({
                "success": True,
                "structure": serializer.data
            })
            
        except Exception as e:
            return Response({
                "success": False,
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'])
    def flat_structure(self, request):
        """
        Retorna todas las carpetas en formato plano (para debugging)
        """
        try:
            carpetas = Carpeta.objects.all().values(
                'id', 'nombre', 'typeFolder', 'id_parent_node', 'compania_id'
            )
            
            return Response({
                "success": True,
                "data": list(carpetas)
            })
            
        except Exception as e:
            return Response({
                "success": False,
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
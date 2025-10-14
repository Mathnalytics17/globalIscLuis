from rest_framework import viewsets
from ..models.index import Carpeta
from ..models.analysis.index import AnalisisLubricante
from ..models.machines.index import Maquina
from ..models.resultsAnalysis.index import ResultadoMuestrasAceite
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from ..serializers.index import CarpetaSerializer, AnalisisLubricanteSerializer, ResultadoMuestrasAceiteSerializer,MaquinaSerializer
from rest_framework.permissions import AllowAny
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import viewsets, status
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend


from rest_framework import permissions



from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction

from apps.activesTree.api.models.index import Empresa

class SyncCompanyRootFolders(APIView):
    """
    Endpoint para sincronizar carpetas root con empresas existentes
    Crea carpetas root automáticamente para empresas que no las tengan
    """
    permission_classes = [AllowAny]
    def post(self, request):
        try:
            with transaction.atomic():
                # Obtener todas las empresas activas
                companies = Empresa.objects.filter(is_active=True)
                # Obtener carpetas root existentes
                existing_roots = Carpeta.objects.filter(typeFolder='root')
                
                # Encontrar empresas que no tienen carpeta root
                companies_without_root = companies.exclude(
                    id__in=existing_roots.values_list('compania_id', flat=True)
                )
                
                created_folders = []
                for company in companies_without_root:
                    folder = Carpeta.objects.create(
                        nombre=company.nombre,
                        typeFolder='root',
                        compania=company,
                        id_parent_node='-1',  # Según tu modelo
                        parentId="root",      # Según tu modelo
                        isMachine=False,
                        is_pt_medida=False
                    )
                    created_folders.append({
                        'id': folder.id,
                        'nombre': folder.nombre,
                        'empresa_id': company.id,
                        'empresa_nombre': company.nombre
                    })
                    print(f"✅ Carpeta root creada: {folder.nombre} para empresa: {company.nombre}")
                
                return Response({
                    'success': True,
                    'message': f'Se crearon {len(created_folders)} carpetas root',
                    'created_folders': created_folders,
                    'total_empresas': companies.count(),
                    'empresas_sin_carpeta': companies_without_root.count()
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            print(f"❌ Error en SyncCompanyRootFolders: {str(e)}")
            return Response({
                'success': False,
                'error': str(e),
                'message': 'Error al sincronizar carpetas root'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





    
class FolderViewSet(viewsets.ModelViewSet):
    """
    API para gestionar carpetas (folders).
    """
    queryset = Carpeta.objects.all()
    serializer_class = CarpetaSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['compania_id', 'typeFolder']
    permission_classes = [AllowAny]

    def get_queryset(self):
        compañia_id = self.request.query_params.get('compania_id')
        typeFolder = self.request.query_params.get('typeFolder')
        nombre = self.request.query_params.get('nombre')

        queryset = Carpeta.objects.all()
        if compañia_id:
            queryset = queryset.filter(compania_id=compañia_id)
        if typeFolder:
            queryset = queryset.filter(typeFolder=typeFolder)
        if nombre:
            queryset = queryset.filter(nombre=nombre)

        return queryset

    def create(self, request, *args, **kwargs):
        """
        Sobrescribe el método POST para mejor manejo de errores
        """
        try:
            print("Datos recibidos para crear carpeta:", request.data)
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except Exception as e:
            print(f"Error en create: {e}")
            return Response(
                {"error": str(e), "detail": "Error al crear la carpeta"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class AnalisisLubricanteViewSet(viewsets.ModelViewSet):
    """
    API para gestionar análisis de lubricantes.
    """
    queryset = AnalisisLubricante.objects.all()
    serializer_class = AnalisisLubricanteSerializer


class ResultadoMuestrasAceiteViewSet(viewsets.ModelViewSet):
    """
    API para gestionar resultados de muestras de aceite.
    """
    queryset = ResultadoMuestrasAceite.objects.all()
    serializer_class = ResultadoMuestrasAceiteSerializer






class MaquinaViewSet(viewsets.ModelViewSet):
    """
    API para gestionar máquinas.
    """
    queryset = Maquina.objects.all()
    serializer_class = MaquinaSerializer
    permission_classes = [AllowAny]  # Acceso público sin autenticación
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]  # Filtros
    filterset_fields = ['nombre', 'tipoAceite', 'numero_serie']  # Campos para filtrar
    search_fields = ['nombre', 'codigo_equipo']  # Campos para búsqueda
    ordering_fields = ['nombre']  # Campos para ordenar
    ordering = ['-nombre']  # Orden por defecto

    @action(detail=True, methods=['post'])
    def cambiar_aceite(self, request, pk=None):
        """
        Acción personalizada para cambiar el aceite de una máquina.
        """
        maquina = self.get_object()
        nuevo_tipo_aceite = request.data.get('tipoAceite')
        if not nuevo_tipo_aceite:
            return Response(
                {"error": "El campo 'tipoAceite' es requerido."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        maquina.tipoAceite = nuevo_tipo_aceite
        maquina.save()
        return Response({"status": "Aceite cambiado correctamente."})

    @action(detail=False, methods=['get'])
    def maquinas_recientes(self, request):
        """
        Acción personalizada para obtener las máquinas creadas en los últimos 7 días.
        """
        from django.utils import timezone
        from datetime import timedelta

        fecha_limite = timezone.now() - timedelta(days=7)
        maquinas = Maquina.objects.filter(fecha_creacion__gte=fecha_limite)
        serializer = self.get_serializer(maquinas, many=True)
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """
        Personaliza la eliminación de una máquina.
        """
        maquina = self.get_object()
        maquina.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)






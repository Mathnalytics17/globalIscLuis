# views.py
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from apps.misc.api.models.extraField.index import ExtraField
from apps.misc.api.serializers.extraField.index import (
    ExtraFieldSerializer, 
    ExtraFieldBulkSerializer,
    ExtraFieldFiltroSerializer
)

class ExtraFieldViewSet(viewsets.ModelViewSet):
    """
    ViewSet para manejar campos extras dinámicos
    """
    queryset = ExtraField.objects.all()
    serializer_class = ExtraFieldSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['tabla_relacionada', 'objeto_id', 'estado', 'tipo_campo']
    search_fields = ['nombre_campo', 'etiqueta', 'descripcion']
    ordering_fields = ['fecha_creacion', 'fecha_actualizacion', 'orden', 'nombre_campo']
    ordering = ['tabla_relacionada', 'objeto_id', 'orden', 'nombre_campo']
    
    def get_queryset(self):
        """
        Personalizar el queryset según permisos y filtros
        """
        queryset = super().get_queryset()
        
        # Filtrar por parámetros de query
        tabla = self.request.query_params.get('tabla_relacionada')
        objeto_id = self.request.query_params.get('objeto_id')
        
        if tabla:
            queryset = queryset.filter(tabla_relacionada=tabla)
        if objeto_id:
            queryset = queryset.filter(objeto_id=objeto_id)
        
        return queryset
    
    @action(detail=False, methods=['post'], url_path='bulk-create')
    def bulk_create(self, request):
        """
        Crear múltiples campos extras a la vez
        """
        serializer = ExtraFieldBulkSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            resultado = serializer.save()
            return Response({
                'mensaje': f'{len(resultado["campos_creados"])} campos creados exitosamente',
                'campos_creados': ExtraFieldSerializer(
                    resultado['campos_creados'], 
                    many=True,
                    context={'request': request}
                ).data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'], url_path='por-objeto')
    def por_objeto(self, request):
        """
        Obtener todos los campos extras de un objeto específico
        """
        filtro_serializer = ExtraFieldFiltroSerializer(data=request.query_params)
        if not filtro_serializer.is_valid():
            return Response(filtro_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        datos_filtro = filtro_serializer.validated_data
        queryset = self.get_queryset()
        
        if 'tabla_relacionada' in datos_filtro:
            queryset = queryset.filter(tabla_relacionada=datos_filtro['tabla_relacionada'])
        if 'objeto_id' in datos_filtro:
            queryset = queryset.filter(objeto_id=datos_filtro['objeto_id'])
        if 'estado' in datos_filtro:
            queryset = queryset.filter(estado=datos_filtro['estado'])
        if 'tipo_campo' in datos_filtro:
            queryset = queryset.filter(tipo_campo=datos_filtro['tipo_campo'])
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], url_path='clonar-campos')
    def clonar_campos(self, request):
        """
        Clonar campos de un objeto a otro
        """
        tabla_origen = request.data.get('tabla_origen')
        objeto_id_origen = request.data.get('objeto_id_origen')
        tabla_destino = request.data.get('tabla_destino')
        objeto_id_destino = request.data.get('objeto_id_destino')
        
        if not all([tabla_origen, objeto_id_origen, tabla_destino, objeto_id_destino]):
            return Response({
                'error': 'Se requieren tabla_origen, objeto_id_origen, tabla_destino y objeto_id_destino'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Buscar campos del objeto origen
        campos_origen = ExtraField.objects.filter(
            tabla_relacionada=tabla_origen,
            objeto_id=objeto_id_origen,
            estado='activo'
        )
        
        campos_clonados = []
        for campo in campos_origen:
            campo_clonado = campo.clonar_para_objeto(objeto_id_destino, request.user)
            campos_clonados.append(campo_clonado)
        
        serializer = self.get_serializer(campos_clonados, many=True)
        return Response({
            'mensaje': f'{len(campos_clonados)} campos clonados exitosamente',
            'campos_clonados': serializer.data
        })
    
    @action(detail=True, methods=['post'], url_path='cambiar-estado')
    def cambiar_estado(self, request, pk=None):
        """
        Cambiar el estado de un campo extra
        """
        campo = self.get_object()
        nuevo_estado = request.data.get('estado')
        
        if nuevo_estado not in dict(ExtraField.ESTADO_OPCIONES):
            return Response({
                'error': f'Estado inválido. Opciones: {list(dict(ExtraField.ESTADO_OPCIONES).keys())}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        campo.estado = nuevo_estado
        campo.usuario_actualizacion = request.user
        campo.save()
        
        serializer = self.get_serializer(campo)
        return Response(serializer.data)
    

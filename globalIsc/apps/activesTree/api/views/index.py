from rest_framework import viewsets
from ..models.index import Carpeta
from ..models.analysis.index import AnalisisLubricante
from ..models.machines.index import Maquina
from ..models.resultsAnalysis.index import ResultadoMuestrasAceite
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from ..serializers.index import CarpetaSerializer, AnalisisLubricanteSerializer, ResultadoMuestrasAceiteSerializer,MaquinaSerializer

from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import viewsets, status
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend


from rest_framework import permissions


    
class FolderViewSet(viewsets.ModelViewSet):
    """
    API para gestionar carpetas (folders).
    """
    queryset = Carpeta.objects.all()
    serializer_class = CarpetaSerializer
    filter_backends = [DjangoFilterBackend]  # Habilitar filtros
    filterset_fields = ['compania_id', 'typeFolder']  # Campos por los que se puede filtrar

    def get_queryset(self):
        # Obtener los parámetros de la URL
        compañia_id = self.request.query_params.get('compania_id')
        typeFolder = self.request.query_params.get('typeFolder')

        # Filtrar el queryset según los parámetros
        queryset = Carpeta.objects.all()
        if compañia_id:
            queryset = queryset.filter(compania_id=compañia_id)
        if typeFolder:
            queryset = queryset.filter(typeFolder=typeFolder)

        return queryset

    def destroy(self, request, *args, **kwargs):
        """
        Sobrescribe el método DELETE para eliminar una carpeta.
        """
        instance = self.get_object()  # Obtener la instancia a eliminar
        self.perform_destroy(instance)  # Eliminar la instancia
        return Response(status=status.HTTP_204_NO_CONTENT)  # Respuesta exitosa sin contenido

    def update(self, request, *args, **kwargs):
        """
        Sobrescribe el método PUT para actualizar una carpeta.
        """
        instance = self.get_object()  # Obtener la instancia a actualizar
        serializer = self.get_serializer(instance, data=request.data, partial=False)  # No permitir actualización parcial
        serializer.is_valid(raise_exception=True)  # Validar los datos
        self.perform_update(serializer)  # Actualizar la instancia

        return Response(serializer.data)  # Devolver los datos actualizados

    def partial_update(self, request, *args, **kwargs):
        """
        Sobrescribe el método PATCH para actualizar parcialmente una carpeta.
        """
        instance = self.get_object()  # Obtener la instancia a actualizar
        serializer = self.get_serializer(instance, data=request.data, partial=True)  # Permitir actualización parcial
        serializer.is_valid(raise_exception=True)  # Validar los datos
        self.perform_update(serializer)  # Actualizar la instancia

        return Response(serializer.data)  # Devolver los datos actualizados

    def perform_destroy(self, instance):
        """
        Lógica adicional antes de eliminar una carpeta.
        """
        # Ejemplo: Registrar la eliminación en un log
        print(f"Eliminando la carpeta: {instance.nombre}")
        super().perform_destroy(instance)  # Llamar al método original

    def perform_update(self, serializer):
        """
        Lógica adicional antes de actualizar una carpeta.
        """
        # Ejemplo: Registrar la actualización en un log
        print(f"Actualizando la carpeta: {serializer.instance.nombre}")
        super().perform_update(serializer)  # Llamar al método original

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
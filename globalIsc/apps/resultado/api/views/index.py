from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from apps.resultado.api.models.index import Resultado, HistoricoResultado, RevisionResultado
from apps.resultado.api.serializers.index import ResultadoSerializer, CreateResultadoSerializer, HistoricoResultadoSerializer, RevisionResultadoSerializer
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from django.utils import timezone


class ResultadoViewSet(viewsets.ModelViewSet):
    queryset = Resultado.objects.all()
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CreateResultadoSerializer
        return ResultadoSerializer
    
    def perform_create(self, serializer):
        serializer.save(usuario_medicion=self.request.user)
    
    @action(detail=True, methods=['post'])
    def revisar(self, request, pk=None):
        resultado = self.get_object()
        estatus_nuevo = request.data.get('estatus')
        observaciones = request.data.get('observaciones', '')
        
        if not estatus_nuevo:
            return Response({'error': 'Se requiere el nuevo estatus'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Crear registro en histórico si hay cambio en el resultado
        if 'resultado' in request.data:
            HistoricoResultado.objects.create(
                resultado=resultado,
                resultado_anterior=resultado.resultado,
                equipo_laboratorio=resultado.equipo_laboratorio,
                fecha_medicion_anterior=resultado.fecha_medicion,
                usuario_medicion=resultado.usuario_medicion,
                observaciones_anterior=resultado.observaciones,
                usuario_modificacion=request.user,
                motivo_cambio=observaciones or 'Modificación durante revisión'
            )
        
        # Crear registro de revisión
        RevisionResultado.objects.create(
            resultado=resultado,
            usuario_revision=request.user,
            estatus_anterior=resultado.estatus,
            estatus_nuevo=estatus_nuevo,
            observaciones=observaciones
        )
        
        # Actualizar resultado
        serializer = CreateResultadoSerializer(resultado, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(serializer.data)

class HistoricoResultadoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = HistoricoResultado.objects.all()
    serializer_class = HistoricoResultadoSerializer

class RevisionResultadoViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RevisionResultado.objects.all()
    serializer_class = RevisionResultadoSerializer

from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from apps.misc.api.models.limitesyaux.index import ElementoAnalisis, CategoriaLimite, LimiteElemento, ComentarioElemento, LimiteViscosidad
from apps.reporte.api.models.index import Interpretacion, DetalleInterpretacion, Reporte
from apps.reporte.api.serializers.index import InterpretacionSerializer, DetalleInterpretacionSerializer, ReporteSerializer, CreateReporteSerializer
from django.utils import timezone

class InterpretacionViewSet(viewsets.ModelViewSet):
    queryset = Interpretacion.objects.all()
    serializer_class = InterpretacionSerializer
    
    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)

class DetalleInterpretacionViewSet(viewsets.ModelViewSet):
    queryset = DetalleInterpretacion.objects.all()
    serializer_class = DetalleInterpretacionSerializer

class ReporteViewSet(viewsets.ModelViewSet):
    queryset = Reporte.objects.all()
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CreateReporteSerializer
        return ReporteSerializer
    
    def perform_create(self, serializer):
        serializer.save(usuario_emision=self.request.user, fecha_emision=timezone.now())
    
    @action(detail=True, methods=['post'])
    def aprobar(self, request, pk=None):
        reporte = self.get_object()
        
        if reporte.estatus != 'pendiente_aprobacion':
            return Response({'error': 'El reporte no está pendiente de aprobación'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        reporte.usuario_aprobacion = request.user
        reporte.fecha_aprobacion = timezone.now()
        reporte.estatus = 'aprobado'
        reporte.save()
        
        return Response(ReporteSerializer(reporte).data)
    
    @action(detail=True, methods=['post'])
    def enviar_aprobacion(self, request, pk=None):
        reporte = self.get_object()
        
        if reporte.estatus != 'borrador':
            return Response({'error': 'Solo reportes en borrador pueden enviarse a aprobación'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        reporte.estatus = 'pendiente_aprobacion'
        reporte.save()
        
        return Response(ReporteSerializer(reporte).data)
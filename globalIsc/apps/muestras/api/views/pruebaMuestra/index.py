from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.muestras.api.serializers.pruebasMuestra.index import PruebaMuestraSerializer, CreatePruebaMuestraSerializer
from django.utils import timezone

from rest_framework.permissions import AllowAny



class PruebaMuestraViewSet(viewsets.ModelViewSet):
    queryset = PruebaMuestra.objects.all()
    permission_classes = [AllowAny]

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CreatePruebaMuestraSerializer
        return PruebaMuestraSerializer

    def perform_create(self, serializer):
        serializer.save(usuario_solicitud=self.request.user)

    # NUEVO: Endpoint para obtener pruebas por muestra específica
    @action(detail=False, methods=['get'], url_path='by-sample/(?P<muestra_id>[^/.]+)')
    def by_sample(self, request, muestra_id=None):
        """
        Obtiene todas las pruebas de una muestra específica
        """
        try:
            sample_tests = PruebaMuestra.objects.filter(
                muestra=muestra_id
            ).select_related('prueba', 'usuario_solicitud')
            
            serializer = self.get_serializer(sample_tests, many=True)
            return Response(serializer.data)
            
        except Exception as e:
            return Response(
                {'error': f'Error al obtener pruebas: {str(e)}'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
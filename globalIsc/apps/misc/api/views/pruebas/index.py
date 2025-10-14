from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from apps.misc.api.models.pruebas.index import Prueba
from apps.misc.api.serializers.pruebas.index import PruebaSerializer
from django.utils import timezone
from apps.misc.api.serializers.limitesyaux.index import AsignarLimiteSerializer,PruebaLimiteSerializer
from apps.misc.api.models.limitesyaux.index import PruebaLimite

from django.contrib.contenttypes.models import ContentType

class PruebaViewSet(viewsets.ModelViewSet):
    queryset = Prueba.objects.all()
    serializer_class = PruebaSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        categoria = self.request.query_params.get('categoria', None)
        
        if categoria:
            queryset = queryset.filter(categoria=categoria)
        return queryset

    @action(detail=True, methods=['post'])
    def asignar_limite(self, request, pk=None):
        prueba = self.get_object()
        serializer = AsignarLimiteSerializer(data=request.data)
        
        if serializer.is_valid():
            content_type_id = serializer.validated_data['content_type_id']
            object_id = serializer.validated_data['object_id']
            
            # Verificar si ya existe un límite para esta prueba
            if PruebaLimite.objects.filter(prueba=prueba).exists():
                return Response(
                    {'error': 'Esta prueba ya tiene un límite asignado'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Crear la relación
            prueba_limite = PruebaLimite.objects.create(
                prueba=prueba,
                content_type_id=content_type_id,
                object_id=object_id
            )
            
            return Response(
                PruebaLimiteSerializer(prueba_limite).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def limite_asignado(self, request, pk=None):
        prueba = self.get_object()
        try:
            prueba_limite = prueba.limite_asignado
            serializer = PruebaLimiteSerializer(prueba_limite)
            return Response(serializer.data)
        except PruebaLimite.DoesNotExist:
            return Response({'detail': 'No hay límite asignado'}, status=404)
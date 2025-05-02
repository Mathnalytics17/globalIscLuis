from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from apps.misc.api.models.pruebas.index import Prueba, RelacionPruebaLimite
from apps.misc.api.serializers.pruebas.index import PruebaSerializer, RelacionPruebaLimiteSerializer
from django.utils import timezone

from django.contrib.contenttypes.models import ContentType
class PruebaViewSet(viewsets.ModelViewSet):
    queryset = Prueba.objects.prefetch_related('relaciones')
    serializer_class = PruebaSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        categoria = self.request.query_params.get('categoria', None)
        
        if categoria:
            queryset = queryset.filter(categoria=categoria)
        return queryset

class RelacionPruebaLimiteViewSet(viewsets.ModelViewSet):
    queryset = RelacionPruebaLimite.objects.all()
    serializer_class = RelacionPruebaLimiteSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        prueba_id = self.request.query_params.get('prueba_id', None)
        tipo_limite = self.request.query_params.get('tipo_limite', None)
        
        if prueba_id:
            queryset = queryset.filter(prueba_id=prueba_id)
        if tipo_limite:
            content_type = ContentType.objects.get(model=tipo_limite.lower())
            queryset = queryset.filter(content_type=content_type)
        return queryset
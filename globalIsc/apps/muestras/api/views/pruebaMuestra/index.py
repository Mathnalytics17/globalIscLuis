from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.muestras.api.serializers.pruebasMuestra.index import PruebaMuestraSerializer, CreatePruebaMuestraSerializer
from django.utils import timezone



class PruebaMuestraViewSet(viewsets.ModelViewSet):
    queryset = PruebaMuestra.objects.all()
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CreatePruebaMuestraSerializer
        return PruebaMuestraSerializer
    
    def perform_create(self, serializer):
        serializer.save(usuario_solicitud=self.request.user)
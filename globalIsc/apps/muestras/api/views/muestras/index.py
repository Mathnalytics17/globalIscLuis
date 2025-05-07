from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.serializers.muestras.index import MuestraSerializer, CreateMuestraSerializer
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated

class MuestraViewSet(viewsets.ModelViewSet):
    queryset = Muestra.objects.all()
    permission_classes = [IsAuthenticated]  # Acceso público sin autenticación
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CreateMuestraSerializer
        return MuestraSerializer
    
    def perform_create(self, serializer):
        serializer.save(usuario_registro=self.request.user)
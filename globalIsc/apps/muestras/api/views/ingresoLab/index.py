from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from apps.muestras.api.models.ingresoLab.index import IngresoLab
from apps.muestras.api.serializers.ingresoLab.index import IngresoLabSerializer, CreateIngresoLabSerializer
from django.utils import timezone
from rest_framework.permissions import AllowAny, IsAuthenticated


class IngresoLabViewSet(viewsets.ModelViewSet):
    queryset = IngresoLab.objects.all()
    permission_classes = [IsAuthenticated] 
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CreateIngresoLabSerializer
        return IngresoLabSerializer
    
    def perform_create(self, serializer):
        serializer.save(usuario_recepcion=self.request.user)
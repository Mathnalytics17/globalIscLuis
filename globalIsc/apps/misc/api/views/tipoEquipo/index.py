from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from apps.misc.api.models.tipoEquipo.index import TipoEquipo, ReferenciaEquipo
from apps.misc.api.serializers.tipoEquipo.index import TipoEquipoSerializer, ReferenciaEquipoSerializer
from django.utils import timezone
from rest_framework.permissions import AllowAny

class TipoEquipoViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]  # Acceso público sin autenticación
    queryset = TipoEquipo.objects.all()
    serializer_class = TipoEquipoSerializer

class ReferenciaEquipoViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]  # Acceso público sin autenticación
    queryset = ReferenciaEquipo.objects.all()
    serializer_class = ReferenciaEquipoSerializer
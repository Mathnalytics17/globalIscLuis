from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from apps.misc.api.models.lubricante.index import Lubricante
from apps.misc.api.serializers.lubricante.index import LubricanteSerializer
from django.utils import timezone

from rest_framework.permissions import AllowAny
class LubricanteViewSet(viewsets.ModelViewSet):
    permission_classes = [AllowAny]  # Acceso público sin autenticación
    queryset = Lubricante.objects.all()
    serializer_class = LubricanteSerializer

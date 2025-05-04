from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from apps.misc.api.models.limitesyaux.index import (
    ElementoAnalisis,
    CategoriaLimite,
    LimiteElemento,
    ComentarioElemento,
    LimiteViscosidad,
    LimiteCalidad
)
from apps.misc.api.serializers.limitesyaux.index import (
    ElementoAnalisisSerializer,
    CategoriaLimiteSerializer,
    LimiteElementoSerializer,
    ComentarioElementoSerializer,
    LimiteViscosidadSerializer,
    LimiteCalidadSerializer
)
from django.utils import timezone
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
# Vista genérica para todos los modelos
class BaseListCreateView(ListCreateAPIView):
    pagination_class = None  # Desactiva paginación para fixtures

class BaseDetailView(RetrieveUpdateDestroyAPIView):
    pass

class ElementoAnalisisViewSet(viewsets.ModelViewSet):
    queryset = ElementoAnalisis.objects.all()
    serializer_class = ElementoAnalisisSerializer

class CategoriaLimiteViewSet(viewsets.ModelViewSet):
    queryset = CategoriaLimite.objects.all()
    serializer_class = CategoriaLimiteSerializer

class LimiteElementoViewSet(viewsets.ModelViewSet):
    queryset = LimiteElemento.objects.all()
    serializer_class = LimiteElementoSerializer

class ComentarioElementoViewSet(viewsets.ModelViewSet):
    queryset = ComentarioElemento.objects.all()
    serializer_class = ComentarioElementoSerializer

# Límites de Viscosidad
class LimiteViscosidadListCreateView(BaseListCreateView):
    queryset = LimiteViscosidad.objects.all()
    serializer_class = LimiteViscosidadSerializer

class LimiteViscosidadRetrieveUpdateDestroyView(BaseDetailView):
    queryset = LimiteViscosidad.objects.all()
    serializer_class = LimiteViscosidadSerializer

# Límites de Calidad
class LimiteCalidadListCreateView(BaseListCreateView):
    queryset = LimiteCalidad.objects.all()
    serializer_class = LimiteCalidadSerializer

class LimiteCalidadRetrieveUpdateDestroyView(BaseDetailView):
    queryset = LimiteCalidad.objects.all()
    serializer_class = LimiteCalidadSerializer

from rest_framework import viewsets
from ...models.index import Marca,  Calidad, Color, MarcaGrasa, NLGI, Jabon, ColorGrasa
from apps.misc.api.serializers.more.index import (MarcaSerializer,ComentarioPredefinidoSerializer, 
                         CalidadSerializer, ColorSerializer, 
                         MarcaGrasaSerializer, NLGISerializer,
                         JabonSerializer, ColorGrasaSerializer)
from apps.misc.api.models.more.index import ComentarioPredefinido


from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView

# Vista genérica para todos los modelos
class BaseListCreateView(ListCreateAPIView):
    pagination_class = None  # Desactiva paginación para fixtures

class BaseDetailView(RetrieveUpdateDestroyAPIView):
    pass

# Marcas
class MarcaListCreateView(BaseListCreateView):
    queryset = Marca.objects.all()
    serializer_class = MarcaSerializer

class MarcaRetrieveUpdateDestroyView(BaseDetailView):
    queryset = Marca.objects.all()
    serializer_class = MarcaSerializer


# Calidades
class CalidadListCreateView(BaseListCreateView):
    queryset = Calidad.objects.all()
    serializer_class = CalidadSerializer

class CalidadRetrieveUpdateDestroyView(BaseDetailView):
    queryset = Calidad.objects.all()
    serializer_class = CalidadSerializer

# Colores (lubricantes)
class ColorListCreateView(BaseListCreateView):
    queryset = Color.objects.all()
    serializer_class = ColorSerializer

class ColorRetrieveUpdateDestroyView(BaseDetailView):
    queryset = Color.objects.all()
    serializer_class = ColorSerializer

# Marcas de Grasa
class MarcaGrasaListCreateView(BaseListCreateView):
    queryset = MarcaGrasa.objects.all()
    serializer_class = MarcaGrasaSerializer

class MarcaGrasaRetrieveUpdateDestroyView(BaseDetailView):
    queryset = MarcaGrasa.objects.all()
    serializer_class = MarcaGrasaSerializer

# NLGI
class NLGIListCreateView(BaseListCreateView):
    queryset = NLGI.objects.all()
    serializer_class = NLGISerializer

class NLGIRetrieveUpdateDestroyView(BaseDetailView):
    queryset = NLGI.objects.all()
    serializer_class = NLGISerializer

# Jabones
class JabonListCreateView(BaseListCreateView):
    queryset = Jabon.objects.all()
    serializer_class = JabonSerializer

class JabonRetrieveUpdateDestroyView(BaseDetailView):
    queryset = Jabon.objects.all()
    serializer_class = JabonSerializer

# Colores de Grasa
class ColorGrasaListCreateView(BaseListCreateView):
    queryset = ColorGrasa.objects.all()
    serializer_class = ColorGrasaSerializer

class ColorGrasaRetrieveUpdateDestroyView(BaseDetailView):
    queryset = ColorGrasa.objects.all()
    serializer_class = ColorGrasaSerializer

# Comentarios Predefinidos
class ComentarioPredefinidoListCreateView(BaseListCreateView):
    queryset = ComentarioPredefinido.objects.filter(activo=True)
    serializer_class = ComentarioPredefinidoSerializer

class ComentarioPredefinidoRetrieveUpdateDestroyView(BaseDetailView):
    queryset = ComentarioPredefinido.objects.all()
    serializer_class = ComentarioPredefinidoSerializer



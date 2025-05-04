from rest_framework import viewsets
from ...models.index import Marca,  Calidad, Color, MarcaGrasa, NLGI, Jabon, ColorGrasa
from apps.misc.api.serializers.more.index import (MarcaSerializer,ComentarioPredefinidoSerializer, 
                         CalidadSerializer, ColorSerializer, 
                         MarcaGrasaSerializer, NLGISerializer,
                         JabonSerializer, ColorGrasaSerializer,SistemaFiltracionSerializer)
from apps.misc.api.models.more.index import ComentarioPredefinido,SistemaFiltracion


from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework import generics
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


class SistemaFiltracionListCreateView(generics.ListCreateAPIView):
    queryset = SistemaFiltracion.objects.all()
    serializer_class = SistemaFiltracionSerializer

class SistemaFiltracionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SistemaFiltracion.objects.all()
    serializer_class = SistemaFiltracionSerializer


from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.contrib.contenttypes.models import ContentType

@api_view(['GET'])
def content_type_detail(request, pk):
    try:
        content_type = ContentType.objects.get(pk=pk)
        data = {
            'id': content_type.id,
            'app_label': content_type.app_label,
            'model': content_type.model,
            
        }
        return Response(data)
    except ContentType.DoesNotExist:
        return Response({'error': 'ContentType not found'}, status=status.HTTP_404_NOT_FOUND)
    
@api_view(['GET'])
def get_all_content_types(request):
    try:
        # Obtener todos los content types
        content_types = ContentType.objects.all().order_by('app_label', 'model')
        
        # Serializar los datos
        data = [
            {
                'id': ct.id,
                'app_label': ct.app_label,
                'model': ct.model,
                'name': str(ct)  # Esto devuelve la representación legible
            }
            for ct in content_types
        ]
        
        return Response(data)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
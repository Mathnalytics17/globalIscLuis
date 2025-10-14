# views.py - Correcciones completas
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.views import APIView  # <-- Agregar esta importación
from django.shortcuts import get_object_or_404
from apps.misc.api.models.limitesyaux.index import (
    ElementoAnalisis,

  
    TiposViscosidad,
    ComentarioElemento,
    LimiteViscosidad,
    LimiteCalidad, 
    LimiteGenericoPrueba,
    TiposCalidad,
    PruebaLimite  # <-- Agregar esta importación
)
from apps.misc.api.models.pruebas.index import Prueba  # <-- Agregar esta importación
from apps.misc.api.serializers.limitesyaux.index import (
    ElementoAnalisisSerializer,
    TipoViscosidadSerializer,
    
    TipoCalidadSerializer,
    ComentarioElementoSerializer,
    LimiteViscosidadSerializer,
    LimiteCalidadSerializer,
    LimiteGenericoSerializer,
    PruebaLimiteSerializer,  # <-- Agregar esta importación
    AsignarLimiteSerializer   # <-- Agregar esta importación
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

# Límites Genéricos - CORREGIR el serializer
class LimiteGenericosListCreateView(BaseListCreateView):
    queryset = LimiteGenericoPrueba.objects.all()
    serializer_class = LimiteGenericoSerializer  # <-- Cambiar de LimiteCalidadSerializer a LimiteGenericoSerializer

class LimiteGenericosRetrieveUpdateDestroyView(BaseDetailView):
    queryset = LimiteGenericoPrueba.objects.all()
    serializer_class = LimiteGenericoSerializer

# Vistas para PruebaLimite
class PruebaLimiteViewSet(viewsets.ModelViewSet):
    queryset = PruebaLimite.objects.all()
    serializer_class = PruebaLimiteSerializer
    
class TipoViscosidadView(viewsets.ModelViewSet):
    queryset = TiposViscosidad.objects.all()
    serializer_class = TipoViscosidadSerializer
    
class TipoCalidadView(viewsets.ModelViewSet):
    queryset = TiposCalidad.objects.all()
    serializer_class = TipoCalidadSerializer
class TiposCalidadRetrieveUpdateDestroyView(BaseDetailView):
    queryset = TiposCalidad.objects.all()
    serializer_class =TipoCalidadSerializer
  
    
class AsignarLimitePruebaView(APIView):
    def post(self, request, prueba_id):
        try:
            prueba = Prueba.objects.get(id=prueba_id)
            serializer = AsignarLimiteSerializer(data=request.data)
            
            if serializer.is_valid():
                content_type_id = serializer.validated_data['content_type_id']
                object_id = serializer.validated_data['object_id']
                
                # Verificar si ya existe un límite para esta prueba
                PruebaLimite.objects.filter(prueba=prueba).delete()
                
                # Crear nueva relación
                prueba_limite = PruebaLimite.objects.create(
                    prueba=prueba,
                    content_type_id=content_type_id,
                    object_id=object_id
                )
                
                return Response(PruebaLimiteSerializer(prueba_limite).data, status=status.HTTP_201_CREATED)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        except Prueba.DoesNotExist:
            return Response({'error': 'Prueba no encontrada'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request, prueba_id):
        try:
            prueba_limite = PruebaLimite.objects.get(prueba_id=prueba_id)
            return Response(PruebaLimiteSerializer(prueba_limite).data)
        except PruebaLimite.DoesNotExist:
            return Response({'limite': None})
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.serializers.muestras.index import MuestraListSerializer,MuestraSerializer, CreateMuestraSerializer
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated, AllowAny

import logging

# Configurar el logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Crear un handler de consola y definir el nivel
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Crear un formato para los mensajes de log
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# Añadir el handler al logger
logger.addHandler(console_handler)

class MuestraViewSetList(viewsets.ModelViewSet):
    queryset = Muestra.objects.all().prefetch_related('resultados', 'resultados__prueba')
    permission_classes = [AllowAny]
    serializer_class = MuestraListSerializer
    
    def list(self, request, *args, **kwargs):
        
    
        try:
            queryset = self.filter_queryset(self.get_queryset())
            serializer = self.get_serializer(queryset, many=True)
            
            # ✅ Ver estructura completa de la primera muestra
            if serializer.data:
                primera_muestra = serializer.data[-1]
                logger.debug("Estructura completa de la primera muestra:")
                logger.debug(primera_muestra)
            
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error en MuestraViewSetList: {str(e)}")
            logger.error("Traceback completo:", exc_info=True)
            return Response(
                {"error": "Error interno del servidor", "detalle": str(e)},
                status=500
            )
    
    
    
class MuestraViewSet(viewsets.ModelViewSet):
    queryset = Muestra.objects.all()
    permission_classes = [AllowAny]
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return CreateMuestraSerializer
        return MuestraSerializer
    
    def create(self, request, *args, **kwargs):
        try:
            # Log para debug
            print("Datos recibidos:", request.data)
            
            serializer = self.get_serializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Si no hay usuario autenticado, usar un usuario por defecto
            if not request.user.is_authenticated:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                default_user = User.objects.first()  # O el usuario que quieras por defecto
                if default_user:
                    serializer.validated_data['usuario_registro'] = default_user
            
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
            
        except Exception as e:
            print("Error al crear muestra:", str(e))
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def perform_create(self, serializer):
        serializer.save()
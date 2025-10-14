from rest_framework import serializers
from apps.muestras.api.serializers.muestras.index import MuestraSerializer
from apps.users.api.serializers.index import UserSerializer
from apps.misc.api.serializers.limitesyaux.index import ElementoAnalisisSerializer
from apps.reporte.api.models.index import Reporte,DetalleInterpretacion,Interpretacion
import base64
import os
from django.core.files.storage import default_storage
class InterpretacionSerializer(serializers.ModelSerializer):
    muestra = MuestraSerializer()
    usuario = UserSerializer()
    
    class Meta:
        model = Interpretacion
        fields = '__all__'

class DetalleInterpretacionSerializer(serializers.ModelSerializer):
    interpretacion = InterpretacionSerializer()
    elemento = ElementoAnalisisSerializer()
    
    class Meta:
        model = DetalleInterpretacion
        fields = '__all__'

class ReporteSerializer(serializers.ModelSerializer):
    muestra = MuestraSerializer()
    usuario_emision = UserSerializer()
    usuario_aprobacion = UserSerializer()
    
    class Meta:
        model = Reporte
        fields = '__all__'

class CreateReporteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reporte
        fields = '__all__'
        read_only_fields = ['consecutivo']

# NUEVO: Serializer con base64 incluido
class ReporteSerializerConBase64(serializers.ModelSerializer):
    firma_base64 = serializers.SerializerMethodField()
    
    class Meta:
        model = Reporte
        fields = '__all__'
    
    def get_firma_base64(self, obj):
        if not obj.firma_ruta:
            return None
        
        try:
            # Construir ruta del archivo
            if obj.firma_ruta.startswith('/media/'):
                file_path = obj.firma_ruta.replace('/media/', '')
            else:
                file_path = obj.firma_ruta
            
            # Verificar si el archivo existe
            if not default_storage.exists(file_path):
                return None
            
            # Leer y convertir a base64
            with default_storage.open(file_path, 'rb') as f:
                file_content = f.read()
                base64_encoded = base64.b64encode(file_content).decode('utf-8')
                
                # Determinar tipo MIME
                if file_path.lower().endswith('.png'):
                    mime_type = 'image/png'
                elif file_path.lower().endswith(('.jpg', '.jpeg')):
                    mime_type = 'image/jpeg'
                else:
                    mime_type = 'image/png'
                
                return f"data:{mime_type};base64,{base64_encoded}"
                
        except Exception as e:
            logger.error(f"Error en serializer firma_base64: {str(e)}")
            return None

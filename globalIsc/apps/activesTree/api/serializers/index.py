
from ..models.index import Carpeta
from ..models.analysis.index import AnalisisLubricante
from apps.activesTree.api.models.machines.index import Maquina


from ..models.resultsAnalysis.index import ResultadoMuestrasAceite
from apps.muestras.api.serializers.index import MuestraSerializer
from apps.muestras.api.models.muestras.index import Muestra

from rest_framework import serializers


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

class MaquinaSerializer(serializers.ModelSerializer):
    muestras = serializers.SerializerMethodField(read_only=True)
    empresa_info = serializers.SerializerMethodField(read_only=True)
  
    class Meta:
        model = Maquina
        fields = '__all__'
    
    def get_muestras(self, obj):
        # Buscar muestras relacionadas con esta máquina
        muestras = Muestra.objects.filter(referencia_equipo=obj)
        return MuestraSerializer(muestras, many=True).data
    
    def get_empresa_info(self, obj):
        # Retornar información de la empresa asociada
        if obj.empresa:
            # Obtener usuarios asociados a la empresa
            usuarios = obj.empresa.user_set.all()
            usuarios_data = [
                {
                    'id': usuario.id,
                    'email': usuario.email,
                    'first_name': usuario.first_name,
                    'last_name': usuario.last_name,
                    'role': usuario.role,
                    'is_active': usuario.is_active,
                    'email_verified': usuario.email_verified,
                    'phone': usuario.phone
                }
                for usuario in usuarios
            ]
            
            return {
                'id': obj.empresa.id,
                'nombre': obj.empresa.nombre,
                'direccion': obj.empresa.direccion,
                'telefono': obj.empresa.telefono,
                'email': obj.empresa.email,
                'is_active': obj.empresa.is_active,
                'usuarios': usuarios_data,
                'total_usuarios': len(usuarios_data)
            }
        return None
class CarpetaSerializer(serializers.ModelSerializer):
    compania_info = serializers.SerializerMethodField(read_only=True)
    machine_info = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Carpeta
        fields = '__all__'

    def get_compania_info(self, obj):
        from apps.misc.api.serializers.companies.index import EmpresaSerializer
        if obj.compania:
            return EmpresaSerializer(obj.compania).data
        return None

    def get_machine_info(self, obj):
        
        if obj.machine:
            return MaquinaSerializer(obj.machine).data
        return None

    def validate(self, data):
        if 'compania' not in data and not self.instance:
            raise serializers.ValidationError({
                "compania": "La compañía es obligatoria"
            })
        return data

    def create(self, validated_data):
        print("✅ Datos validados para crear carpeta:", validated_data)
        try:
            instance = super().create(validated_data)
            print("✅ Carpeta creada exitosamente:", instance.id)
            return instance
        except Exception as e:
            print("❌ Error al crear carpeta:", e)
            raise
  
class AnalisisLubricanteSerializer(serializers.ModelSerializer):
    Maquina= MaquinaSerializer()  # Incluye los datos del análisis relacionado
    class Meta:
        model = AnalisisLubricante
        fields = '__all__'


class ResultadoMuestrasAceiteSerializer(serializers.ModelSerializer):
    analisis = AnalisisLubricanteSerializer()  # Incluye los datos del análisis relacionado

    class Meta:
        model = ResultadoMuestrasAceite
        fields = '__all__'
        


        

 

class ActiveTreesSerializer(serializers.ModelSerializer):
       class Meta:
        model = Carpeta
        fields = '__all__'
    
    
        



    










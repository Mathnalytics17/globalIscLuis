from rest_framework import serializers
from apps.muestras.api.serializers.pruebasMuestra.index import PruebaMuestraSerializer
from apps.users.api.serializers.index import UserSerializer
from apps.resultado.api.models.index import Resultado, HistoricoResultado, RevisionResultado, VersionInterpretacion

class ResultadoSerializer(serializers.ModelSerializer):
    prueba_muestra = PruebaMuestraSerializer()
    
    usuario_medicion = UserSerializer()
    
    class Meta:
        model = Resultado
        fields = '__all__'

class CreateResultadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resultado
        fields = '__all__'
        read_only_fields = ['fecha_registro', 'fecha_actualizacion']

class HistoricoResultadoSerializer(serializers.ModelSerializer):
    resultado = ResultadoSerializer()
   
    usuario_medicion = UserSerializer()
    usuario_modificacion = UserSerializer()
    
    class Meta:
        model = HistoricoResultado
        fields = '__all__'

class RevisionResultadoSerializer(serializers.ModelSerializer):
    resultado = ResultadoSerializer()
    usuario_revision = UserSerializer()
    
    class Meta:
        model = RevisionResultado
        fields = '__all__'


class VersionInterpretacionSerializer(serializers.ModelSerializer):
    creado_por_nombre = serializers.SerializerMethodField()

    class Meta:
        model = VersionInterpretacion
        fields = [
            "id", "muestra", "version", "contenido", "motivo", "origen",
            "creado_por", "creado_por_nombre", "creado_en",
        ]
        read_only_fields = fields

    def get_creado_por_nombre(self, obj):
        if not obj.creado_por:
            return "Sistema"
        return obj.creado_por.get_full_name() or obj.creado_por.email

from rest_framework import serializers
from apps.misc.api.serializers.pruebas.index import PruebaSerializer
from apps.muestras.api.serializers.pruebasMuestra.index import PruebaMuestraSerializer
from apps.users.api.serializers.index import UserSerializer
from apps.resultado.api.models.index import Resultado, HistoricoResultado, RevisionResultado

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

from rest_framework import serializers

from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.misc.api.serializers.pruebas.index import PruebaSerializer
from apps.users.api.serializers.index import UserSerializer
class PruebaMuestraSerializer(serializers.ModelSerializer):
    prueba = PruebaSerializer()
    usuario_solicitud = UserSerializer()
    
    class Meta:
        model = PruebaMuestra
        fields = '__all__'

class CreatePruebaMuestraSerializer(serializers.ModelSerializer):
    class Meta:
        model = PruebaMuestra
        fields = '__all__'
        read_only_fields = ['fecha_solicitud', 'usuario_solicitud']



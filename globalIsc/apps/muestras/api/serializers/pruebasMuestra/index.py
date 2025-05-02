
from rest_framework import serializers
from apps.misc.api.serializers.pruebas.index import PruebaSerializer
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra

from apps.users.api.serializers.index import UserSerializer
from apps.muestras.api.models.muestras.index import Muestra

from apps.muestras.api.serializers.muestras.index import MuestraSerializer
class PruebaMuestraSerializer(serializers.ModelSerializer):
    prueba = PruebaSerializer()
    usuario_solicitud = UserSerializer()
    muestra=MuestraSerializer()
    
    class Meta:
        model = PruebaMuestra
        fields = '__all__'

class CreatePruebaMuestraSerializer(serializers.ModelSerializer):
    class Meta:
        model = PruebaMuestra
        fields = '__all__'
        read_only_fields = ['fecha_solicitud']
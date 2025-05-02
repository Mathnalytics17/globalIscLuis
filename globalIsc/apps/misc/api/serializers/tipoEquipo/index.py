from rest_framework import serializers
from apps.misc.api.models.tipoEquipo.index import TipoEquipo, ReferenciaEquipo

class TipoEquipoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoEquipo
        fields = '__all__'

class ReferenciaEquipoSerializer(serializers.ModelSerializer):
    tipo = TipoEquipoSerializer()
    
    class Meta:
        model = ReferenciaEquipo
        fields = '__all__'
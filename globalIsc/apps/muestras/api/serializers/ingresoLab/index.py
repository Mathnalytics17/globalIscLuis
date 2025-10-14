from rest_framework import serializers

from apps.muestras.api.models.ingresoLab.index import IngresoLab

class IngresoLabSerializer(serializers.ModelSerializer):

    
    class Meta:
        model = IngresoLab
        fields = '__all__'

class CreateIngresoLabSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngresoLab
        fields = '__all__'
        read_only_fields = ['fecha_registro']
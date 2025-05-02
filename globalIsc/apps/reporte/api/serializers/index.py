from rest_framework import serializers
from apps.muestras.api.serializers.muestras.index import MuestraSerializer
from apps.users.api.serializers.index import UserSerializer
from apps.misc.api.serializers.limitesyaux.index import ElementoAnalisisSerializer
from apps.reporte.api.models.index import Reporte,DetalleInterpretacion,Interpretacion

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
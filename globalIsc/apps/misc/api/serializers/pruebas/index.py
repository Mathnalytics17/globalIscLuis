from rest_framework import serializers
from apps.misc.api.models.pruebas.index import Prueba
from apps.misc.api.serializers.limitesyaux.index import LimiteCalidadSerializer,LimiteViscosidadSerializer
from apps.misc.api.models.pruebas.index import RelacionPruebaLimite
from apps.misc.api.models.limitesyaux.index import LimiteViscosidad,LimiteCalidad

class RelacionPruebaLimiteSerializer(serializers.ModelSerializer):
    limite_data = serializers.SerializerMethodField()
    
    class Meta:
        model = RelacionPruebaLimite
        fields = '__all__'
    
    def get_limite_data(self, obj):
        if isinstance(obj.limite, LimiteViscosidad):
            return LimiteViscosidadSerializer(obj.limite).data
        elif isinstance(obj.limite, LimiteCalidad):
            return LimiteCalidadSerializer(obj.limite).data
        return None

class PruebaSerializer(serializers.ModelSerializer):
    relaciones = serializers.SerializerMethodField()
    
    class Meta:
        model = Prueba
        fields = '__all__'
    
    def get_relaciones(self, obj):
        relaciones = RelacionPruebaLimite.objects.filter(prueba=obj)
        return RelacionPruebaLimiteSerializer(relaciones, many=True).data



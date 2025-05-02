
from rest_framework import serializers
from ...models.index import Marca, Calidad, Color, MarcaGrasa, NLGI, Jabon, ColorGrasa
from apps.misc.api.models.more.index import ComentarioPredefinido

class MarcaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marca
        fields = '__all__'

class ComentarioPredefinidoSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    
    class Meta:
        model = ComentarioPredefinido
        fields = ['id', 'texto', 'tipo', 'tipo_display', 'activo']
        read_only_fields = ['id', 'tipo_display']
class CalidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Calidad
        fields = '__all__'

class ColorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Color
        fields = '__all__'

class MarcaGrasaSerializer(serializers.ModelSerializer):
    color = serializers.StringRelatedField()
    
    class Meta:
        model = MarcaGrasa
        fields = '__all__'

class NLGISerializer(serializers.ModelSerializer):
    class Meta:
        model = NLGI
        fields = '__all__'

class JabonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Jabon
        fields = '__all__'

class ColorGrasaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ColorGrasa
        fields = '__all__'
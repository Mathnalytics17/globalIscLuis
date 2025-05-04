from rest_framework import serializers
from ...models.limitesyaux.index import (
    ElementoAnalisis,CategoriaLimite,LimiteElemento,ComentarioElemento,
    LimiteViscosidad,LimiteCalidad)
from apps.muestras.api.serializers.muestras.index import MuestraSerializer
from apps.users.api.serializers.index import UserSerializer
class ElementoAnalisisSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElementoAnalisis
        fields = '__all__'

class CategoriaLimiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaLimite
        fields = '__all__'

class LimiteElementoSerializer(serializers.ModelSerializer):
    elemento = ElementoAnalisisSerializer()
    categoria = CategoriaLimiteSerializer()
    
    class Meta:
        model = LimiteElemento
        fields = '__all__'

class ComentarioElementoSerializer(serializers.ModelSerializer):
    elemento = ElementoAnalisisSerializer()
    categoria = CategoriaLimiteSerializer()
    
    class Meta:
        model = ComentarioElemento
        fields = '__all__'

class LimiteViscosidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = LimiteViscosidad
        fields = '__all__'

class LimiteCalidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = LimiteCalidad
        fields = '__all__'


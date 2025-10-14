from rest_framework import serializers
from django.contrib.contenttypes.models import ContentType
from ...models.limitesyaux.index import (
    ElementoAnalisis,ComentarioElemento,LimiteGenericoPrueba,
    LimiteViscosidad,LimiteCalidad,PruebaLimite,TiposViscosidad,TiposCalidad)



from apps.misc.api.models.pruebas.index import Prueba
class ElementoAnalisisSerializer(serializers.ModelSerializer):
    class Meta:
        model = ElementoAnalisis
        fields = '__all__'



class ComentarioElementoSerializer(serializers.ModelSerializer):
    elemento = ElementoAnalisisSerializer()
    
    class Meta:
        model = ComentarioElemento
        fields = '__all__'

class LimiteViscosidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = LimiteViscosidad
        fields = '__all__'


        
        
class LimiteGenericoSerializer(serializers.ModelSerializer):
    class Meta:
        model = LimiteGenericoPrueba
        fields = '__all__'


class TipoViscosidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = TiposViscosidad
        fields = '__all__'




class LimiteCalidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = LimiteCalidad
        fields = '__all__'
        
class TipoCalidadSerializer(serializers.ModelSerializer):
    class Meta:
        model=TiposCalidad
        fields='__all__'


class LimiteGenericoPruebaSerializer(serializers.ModelSerializer):
    class Meta:
        model = LimiteGenericoPrueba
        fields = '__all__'

class PruebaLimiteSerializer(serializers.ModelSerializer):
    limite = serializers.SerializerMethodField()
    
    class Meta:
        model = PruebaLimite
        fields = '__all__'
    
    def get_limite(self, obj):
        limite_obj = obj.limite
        if not limite_obj:
            return None
        
        content_type = ContentType.objects.get_for_model(limite_obj)
        
        if content_type.model == 'limitegenericoprueba':
            return LimiteGenericoPruebaSerializer(limite_obj).data
        elif content_type.model == 'limitecalidad':
            return LimiteCalidadSerializer(limite_obj).data
        elif content_type.model == 'limiteviscosidad':
            return LimiteViscosidadSerializer(limite_obj).data
        elif content_type.model == 'elementoanalisis':
            return ElementoAnalisisSerializer(limite_obj).data
        else:
            return {'tipo': 'desconocido', 'object_id': obj.object_id}

class AsignarLimiteSerializer(serializers.Serializer):
    content_type_id = serializers.IntegerField()
    object_id = serializers.IntegerField()

    def validate(self, data):
        try:
            content_type = ContentType.objects.get(id=data['content_type_id'])
            model_class = content_type.model_class()
            # Verificar que el objeto existe
            model_class.objects.get(id=data['object_id'])
        except ContentType.DoesNotExist:
            raise serializers.ValidationError("Tipo de contenido no válido")
        except model_class.DoesNotExist:
            raise serializers.ValidationError("El límite especificado no existe")
        return data
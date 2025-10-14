# serializers.py
from rest_framework import serializers
from apps.misc.api.models.extraField.index import ExtraField
from django.contrib.auth import get_user_model

User = get_user_model()

class ExtraFieldSerializer(serializers.ModelSerializer):
    valor_actual = serializers.SerializerMethodField(read_only=True)
    usuario_creacion_info = serializers.SerializerMethodField(read_only=True)
    usuario_actualizacion_info = serializers.SerializerMethodField(read_only=True)
    usuario_ultima_edicion_info = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = ExtraField
        fields = '__all__'
        read_only_fields = [
            'fecha_creacion', 
            'fecha_actualizacion', 
            'fecha_ultima_edicion',
            'version'
        ]
    
    def get_valor_actual(self, obj):
        """Devuelve el valor formateado según el tipo"""
        return obj.get_valor()
    
    def get_usuario_creacion_info(self, obj):
        if obj.usuario_creacion:
            return {
                'id': obj.usuario_creacion.id,
                'email': obj.usuario_creacion.email,
                'nombre_completo': f"{obj.usuario_creacion.first_name} {obj.usuario_creacion.last_name}".strip()
            }
        return None
    
    def get_usuario_actualizacion_info(self, obj):
        if obj.usuario_actualizacion:
            return {
                'id': obj.usuario_actualizacion.id,
                'email': obj.usuario_actualizacion.email,
                'nombre_completo': f"{obj.usuario_actualizacion.first_name} {obj.usuario_actualizacion.last_name}".strip()
            }
        return None
    
    def get_usuario_ultima_edicion_info(self, obj):
        if obj.usuario_ultima_edicion:
            return {
                'id': obj.usuario_ultima_edicion.id,
                'email': obj.usuario_ultima_edicion.email,
                'nombre_completo': f"{obj.usuario_ultima_edicion.first_name} {obj.usuario_ultima_edicion.last_name}".strip()
            }
        return None
    
    def validate(self, data):
        """Validación personalizada"""
        # Validar que el valor coincida con el tipo
        tipo_campo = data.get('tipo_campo', self.instance.tipo_campo if self.instance else None)
        
        if tipo_campo == 'numero' and data.get('valor_texto'):
            try:
                float(data['valor_texto'])
            except (ValueError, TypeError):
                raise serializers.ValidationError({
                    'valor_texto': 'El valor debe ser un número válido'
                })
        
        return data
    
    def create(self, validated_data):
        # Asignar usuario de creación desde el contexto
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['usuario_creacion'] = request.user
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        # Actualizar información de auditoría
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            validated_data['usuario_actualizacion'] = request.user
            validated_data['usuario_ultima_edicion'] = request.user
            validated_data['fecha_ultima_edicion'] = serializers.DateTimeField().to_representation(
                serializers.DateTimeField().to_internal_value(None)
            )
        
        # Incrementar versión
        validated_data['version'] = instance.version + 1
        
        return super().update(instance, validated_data)

class ExtraFieldBulkSerializer(serializers.Serializer):
    """
    Serializer para crear/actualizar múltiples campos extras a la vez
    """
    campos = ExtraFieldSerializer(many=True)
    
    def create(self, validated_data):
        campos_data = validated_data.pop('campos')
        campos_creados = []
        
        for campo_data in campos_data:
            serializer = ExtraFieldSerializer(
                data=campo_data, 
                context=self.context
            )
            if serializer.is_valid():
                campo = serializer.save()
                campos_creados.append(campo)
        
        return {'campos_creados': campos_creados}

class ExtraFieldFiltroSerializer(serializers.Serializer):
    """
    Serializer para filtrar campos extras
    """
    tabla_relacionada = serializers.CharField(required=False)
    objeto_id = serializers.CharField(required=False)
    estado = serializers.ChoiceField(
        choices=ExtraField.ESTADO_OPCIONES, 
        required=False
    )
    tipo_campo = serializers.ChoiceField(
        choices=ExtraField.TIPO_CAMPO_OPCIONES, 
        required=False
    )
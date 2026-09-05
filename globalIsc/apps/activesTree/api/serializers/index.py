from rest_framework import serializers

from apps.activesTree.api.models.index import Carpeta, PuntoMuestreo, AsignacionPuntoMuestreo
from apps.activesTree.api.models.machines.index import Maquina
from apps.muestras.api.serializers.muestras.index import MuestraListSerializer
from apps.users.api.models.index import User


class MaquinaSerializer(serializers.ModelSerializer):
    empresa_info = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Maquina
        fields = '__all__'

    def get_empresa_info(self, obj):
        if not obj.empresa:
            return None
        return {
            'id': obj.empresa.id,
            'nombre': obj.empresa.nombre,
            'direccion': obj.empresa.direccion,
            'telefono': obj.empresa.telefono,
            'email': obj.empresa.email,
            'is_active': obj.empresa.is_active,
        }


class MaquinaConMuestrasSerializer(MaquinaSerializer):
    muestras = serializers.SerializerMethodField(read_only=True)

    class Meta(MaquinaSerializer.Meta):
        fields = '__all__'

    def get_muestras(self, obj):
        return MuestraListSerializer(obj.muestra_set.all(), many=True).data


class CarpetaSerializer(serializers.ModelSerializer):
    compania_info = serializers.SerializerMethodField(read_only=True)
    machine_info = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Carpeta
        fields = '__all__'

    def get_compania_info(self, obj):
        if not obj.compania:
            return None
        return {
            'id': obj.compania.id,
            'nombre': obj.compania.nombre,
            'direccion': obj.compania.direccion,
            'telefono': obj.compania.telefono,
            'email': obj.compania.email,
        }

    def get_machine_info(self, obj):
        if not obj.machine:
            return None
        return MaquinaSerializer(obj.machine).data

    def validate(self, data):
        if 'compania' not in data and not self.instance:
            raise serializers.ValidationError({'compania': 'La compania es obligatoria'})
        return data


class PuntoMuestreoSerializer(serializers.ModelSerializer):
    maquina_nombre = serializers.CharField(source='maquina.nombre', read_only=True)
    empresa_id = serializers.IntegerField(source='maquina.empresa_id', read_only=True)
    muestras_asociadas = serializers.SerializerMethodField()

    class Meta:
        model = PuntoMuestreo
        fields = [
            'id', 'maquina', 'maquina_nombre', 'empresa_id', 'nombre', 'codigo',
            'descripcion', 'activo', 'muestras_asociadas', 'creado_por',
            'creado_en', 'actualizado_en',
        ]
        read_only_fields = ['creado_por', 'creado_en', 'actualizado_en']

    def get_muestras_asociadas(self, obj):
        return getattr(obj, 'muestras_asociadas', obj.asignaciones.filter(activa=True).count())

    def validate_maquina(self, maquina):
        request = self.context.get('request')
        user = getattr(request, 'user', None)
        if user and not (user.is_superuser or user.role == User.Role.GLOBAL):
            if maquina.empresa_id != getattr(user, 'empresa_id', None):
                raise serializers.ValidationError('La maquina no pertenece a su empresa.')
        return maquina


class AsignacionPuntoMuestreoSerializer(serializers.ModelSerializer):
    muestra_id = serializers.CharField(source='muestra.id', read_only=True)
    lote_id = serializers.CharField(source='muestra.lote_id', read_only=True)
    punto_nombre = serializers.CharField(source='punto_muestreo.nombre', read_only=True)
    maquina_id = serializers.IntegerField(source='punto_muestreo.maquina_id', read_only=True)

    class Meta:
        model = AsignacionPuntoMuestreo
        fields = [
            'id', 'muestra_id', 'lote_id', 'punto_muestreo', 'punto_nombre',
            'maquina_id', 'origen', 'activa', 'asignado_por', 'asignado_en',
            'finalizado_en',
        ]

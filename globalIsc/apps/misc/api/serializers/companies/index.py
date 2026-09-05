from rest_framework import serializers
from apps.misc.api.models.companies.index import Empresa
from apps.activesTree.api.serializers.index import MaquinaSerializer


class EmpresaSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='nombre', read_only=True)
    address = serializers.CharField(source='direccion', read_only=True)
    phone = serializers.CharField(source='telefono', read_only=True)
    created_at = serializers.DateTimeField(source='fecha_creacion', read_only=True)
    maquinas = MaquinaSerializer(many=True, read_only=True, source='maquina_set')
    total_maquinas = serializers.IntegerField(read_only=True, source='maquina_set.count')
    usuarios = serializers.SerializerMethodField(read_only=True)
    total_usuarios = serializers.IntegerField(read_only=True, source='user_set.count')
    admin_email = serializers.EmailField(write_only=True, required=False, allow_blank=True)
    admin_role = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    transfer_existing_admin = serializers.BooleanField(write_only=True, required=False, default=False)
    
    class Meta:
        model = Empresa
        fields = '__all__'

    def to_internal_value(self, data):
        if hasattr(data, 'copy'):
            data = data.copy()
        alias_map = {
            'name': 'nombre',
            'address': 'direccion',
            'phone': 'telefono',
        }
        for alias, canonical in alias_map.items():
            if alias in data and canonical not in data:
                data[canonical] = data[alias]
        return super().to_internal_value(data)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hacer todos los campos opcionales excepto 'nombre'
        for field_name, field in self.fields.items():
            if field_name != 'nombre':
                field.required = False
                if hasattr(field, 'allow_blank'):
                    field.allow_blank = True
                if hasattr(field, 'allow_null'):
                    field.allow_null = True

    def validate_nombre(self, value):
        """
        Validación específica para el campo nombre
        """
        if not value or not value.strip():
            raise serializers.ValidationError("El nombre es obligatorio")
        return value.strip()

    def validate_admin_email(self, value):
        if value:
            return value.strip().lower()
        return value
    
    def get_usuarios(self, obj):
        """
        Retorna información de los usuarios asociados a la empresa
        """
        usuarios = obj.user_set.all()  # Esto asume que el related_name es 'user_set'
        return [
            {
                'id': usuario.id,
                'email': usuario.email,
                'first_name': usuario.first_name,
                'last_name': usuario.last_name,
                'role': usuario.role,
                'is_active': usuario.is_active,
                'email_verified': usuario.email_verified,
                'phone': usuario.phone
            }
            for usuario in usuarios
        ]

from rest_framework import serializers
from ..models.index import Usuario
from django.contrib.auth.hashers import make_password


class UsuarioSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = Usuario
        fields = ['id', 'username', 'email', 'password', 'empresa', 'rol']

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        return super().create(validated_data)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model=Usuario
        fields=['id', 'username', 'email', 'password', 'empresa', 'rol']
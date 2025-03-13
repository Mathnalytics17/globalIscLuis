from rest_framework import serializers
from ...models.roles.index import Rol



class RolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = '__all__'
from rest_framework import serializers
from ...models.companies.index import Empresa
from .....activesTree.api.serializers.index import CarpetaSerializer
class EmpresaSerializer(serializers.ModelSerializer):
    carpetas = CarpetaSerializer(many=True, read_only=True)
    class Meta:
        model = Empresa
        fields = '__all__'

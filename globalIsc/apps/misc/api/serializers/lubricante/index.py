from rest_framework import serializers
from apps.misc.api.models.lubricante.index import Lubricante


class LubricanteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lubricante
        fields = '__all__'
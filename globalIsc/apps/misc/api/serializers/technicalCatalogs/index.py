from rest_framework import serializers

from apps.misc.api.models.technicalCatalogs.index import (
    Condicion,
    EquipoPrueba,
    MetodoEquipo,
    Unidad,
)


class EquipoPruebaSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipoPrueba
        fields = "__all__"


class UnidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Unidad
        fields = "__all__"


class MetodoEquipoSerializer(serializers.ModelSerializer):
    equipo_prueba_info = EquipoPruebaSerializer(source="equipo_prueba", read_only=True)

    class Meta:
        model = MetodoEquipo
        fields = "__all__"


class CondicionSerializer(serializers.ModelSerializer):
    unidad_info = UnidadSerializer(source="unidad", read_only=True)

    class Meta:
        model = Condicion
        fields = "__all__"

from rest_framework import serializers

from apps.misc.api.models.technicalCatalogs.index import (
    CategoriaUnidad,
    Condicion,
    EquipoPrueba,
    MetodoEquipo,
    Unidad,
)


class EquipoPruebaSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipoPrueba
        fields = "__all__"


class CategoriaUnidadSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaUnidad
        fields = "__all__"

    def validate_nombre(self, value):
        value = " ".join((value or "").split())
        if not value:
            raise serializers.ValidationError("El nombre de la categoría es obligatorio.")
        existing = CategoriaUnidad.objects.filter(nombre__iexact=value)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("Ya existe una categoría con ese nombre.")
        return value


class UnidadSerializer(serializers.ModelSerializer):
    categoria_info = CategoriaUnidadSerializer(source="categoria", read_only=True)

    class Meta:
        model = Unidad
        fields = "__all__"

    def validate(self, attrs):
        category = attrs.get("categoria", getattr(self.instance, "categoria", None))
        supplied_legacy_label = attrs.get("magnitud") if "magnitud" in self.initial_data else None

        if category is None:
            raise serializers.ValidationError({"categoria": "Seleccione una categoría administrada."})

        if not category.activo and not (self.instance and self.instance.categoria_id == category.id):
            raise serializers.ValidationError({"categoria": "La categoría seleccionada está inactiva."})

        if supplied_legacy_label is not None:
            normalized_label = " ".join(str(supplied_legacy_label).split()).casefold()
            if normalized_label and normalized_label != category.nombre.casefold():
                raise serializers.ValidationError({"magnitud": "La categoría debe coincidir con la categoría seleccionada."})

        # Keep legacy read clients and exports consistent while making the
        # foreign key the source of truth.
        attrs["magnitud"] = category.nombre
        return attrs


class MetodoEquipoSerializer(serializers.ModelSerializer):
    equipo_prueba_info = EquipoPruebaSerializer(source="equipo_prueba", read_only=True)

    class Meta:
        model = MetodoEquipo
        fields = "__all__"


class CondicionSerializer(serializers.ModelSerializer):
    unidad_info = UnidadSerializer(source="unidad", read_only=True)
    magnitud_info = CategoriaUnidadSerializer(source="magnitud_categoria", read_only=True)

    class Meta:
        model = Condicion
        fields = "__all__"

    def validate(self, attrs):
        category = attrs.get("magnitud_categoria", getattr(self.instance, "magnitud_categoria", None))
        unit = attrs.get("unidad", getattr(self.instance, "unidad", None))
        # ``magnitud`` has a model default for legacy records. DRF places that
        # default in validated data even when a modern client did not send the
        # legacy field, so validate it only when it was explicitly supplied.
        supplied_legacy_label = attrs.get("magnitud") if "magnitud" in self.initial_data else None

        if category is None:
            raise serializers.ValidationError({"magnitud_categoria": "Seleccione una magnitud administrada."})
        if unit is None:
            raise serializers.ValidationError({"unidad": "Seleccione una unidad de medida."})
        if not category.activo and not (self.instance and self.instance.magnitud_categoria_id == category.id):
            raise serializers.ValidationError({"magnitud_categoria": "La magnitud seleccionada está inactiva."})
        if unit.categoria_id != category.id:
            raise serializers.ValidationError({"unidad": "La unidad debe pertenecer a la magnitud seleccionada."})
        if supplied_legacy_label is not None:
            normalized_label = " ".join(str(supplied_legacy_label).split()).casefold()
            if normalized_label and normalized_label != category.nombre.casefold():
                raise serializers.ValidationError({"magnitud": "La magnitud debe coincidir con la selección administrada."})

        attrs["magnitud"] = category.nombre
        return attrs

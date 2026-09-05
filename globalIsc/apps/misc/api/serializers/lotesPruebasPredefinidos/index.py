import json

from rest_framework import serializers

from apps.misc.api.models.lotesPruebasPredefinidos.index import (
    LotePruebasPredefinido,
    LotePruebasPredefinidoDetalle,
)
from apps.misc.api.models.pruebas.index import Prueba
from apps.misc.api.models.dynamicTechnicalConfig.index import PruebaFuenteLimite, PruebaLimiteCampo
from apps.misc.api.models.technicalCatalogs.index import Condicion, EquipoPrueba, MetodoEquipo
from apps.misc.api.serializers.pruebas.index import format_condition_label
from apps.misc.api.serializers.technicalCatalogs.index import (
    CondicionSerializer,
    EquipoPruebaSerializer,
    MetodoEquipoSerializer,
)
from apps.misc.api.serializers.tipoGestionMuestra.index import TipoGestionMuestraSerializer


class FlexibleCriterionValueField(serializers.Field):
    def to_internal_value(self, data):
        if data in [None, ""]:
            return None
        if isinstance(data, (dict, list)):
            return json.dumps(data, ensure_ascii=False)
        return str(data).strip()

    def to_representation(self, value):
        if value in [None, ""]:
            return None
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(str(value))
        except (TypeError, ValueError):
            return value


class LotePruebasPredefinidoDetalleSerializer(serializers.ModelSerializer):
    prueba_info = serializers.SerializerMethodField()
    equipo_prueba_info = EquipoPruebaSerializer(source="equipo_prueba", read_only=True)
    metodo_equipo_info = MetodoEquipoSerializer(source="metodo_equipo", read_only=True)
    condicion_info = CondicionSerializer(source="condicion", read_only=True)
    criterio_limite_valor = FlexibleCriterionValueField(required=False, allow_null=True)

    class Meta:
        model = LotePruebasPredefinidoDetalle
        fields = [
            "id",
            "prueba",
            "prueba_info",
            "equipo_prueba",
            "equipo_prueba_info",
            "metodo_equipo",
            "metodo_equipo_info",
            "condicion",
            "condicion_info",
            "condicion_texto",
            "unidad",
            "configuracion_resultados",
            "criterio_limite_catalogo",
            "criterio_limite_item",
            "criterio_limite_escala",
            "criterio_limite_escala_item",
            "criterio_limite_valor",
            "orden",
            "activo",
        ]

    def get_prueba_info(self, obj):
        prueba = obj.prueba
        metodo = getattr(prueba, "metodo", None)
        equipo = getattr(metodo, "equipo_prueba", None) if metodo else None
        return {
            "id": prueba.id,
            "nombre_variable": prueba.nombre_variable,
            "acronimo": prueba.acronimo,
            "unidad_medida": prueba.unidad_medida,
            "condicion": prueba.condicion,
            "metodo": metodo.id if metodo else None,
            "metodo_nombre": getattr(metodo, "nombre", None),
            "equipo_prueba": equipo.id if equipo else None,
            "equipo_prueba_nombre": getattr(equipo, "nombre", None),
        }

    def validate(self, attrs):
        prueba = attrs.get("prueba") or getattr(self.instance, "prueba", None)
        metodo = attrs.get("metodo_equipo") or getattr(self.instance, "metodo_equipo", None)
        equipo = attrs.get("equipo_prueba") or getattr(self.instance, "equipo_prueba", None)
        condicion = attrs.get("condicion") or getattr(self.instance, "condicion", None) or getattr(prueba, "condicion_catalogo", None)

        if metodo and equipo and metodo.equipo_prueba_id != equipo.id:
            raise serializers.ValidationError({"metodo_equipo": "El método no pertenece al equipo seleccionado."})

        attrs["equipo_prueba"] = equipo or (metodo.equipo_prueba if metodo else None)
        attrs["metodo_equipo"] = metodo
        attrs["condicion"] = condicion

        if not attrs.get("condicion_texto"):
            attrs["condicion_texto"] = (
                format_condition_label(condicion)
                or getattr(prueba, "condicion", None)
                or None
            )
        criterio_item = attrs.get("criterio_limite_item") or getattr(self.instance, "criterio_limite_item", None)
        criterio_catalogo = attrs.get("criterio_limite_catalogo") or getattr(self.instance, "criterio_limite_catalogo", None)
        has_catalog_source = bool(prueba) and PruebaFuenteLimite.objects.filter(
            prueba=prueba,
            tipo_limite__in=["catalogo", "campo_muestra", "seleccion_asignacion"],
            activo=True,
            deleted_at__isnull=True,
        ).exists()
        if not has_catalog_source:
            criterio_item = None
            criterio_catalogo = None
            attrs["criterio_limite_item"] = None
            attrs["criterio_limite_catalogo"] = None
        if criterio_item and criterio_catalogo and criterio_item.catalogo_id != criterio_catalogo.id:
            raise serializers.ValidationError({"criterio_limite_item": "El criterio seleccionado no pertenece al catálogo indicado."})
        if criterio_item and not criterio_catalogo:
            criterio_catalogo = criterio_item.catalogo
            attrs["criterio_limite_catalogo"] = criterio_catalogo
        if criterio_catalogo and prueba and not PruebaFuenteLimite.objects.filter(
            prueba=prueba,
            catalogo_fuente=criterio_catalogo,
            tipo_limite__in=["catalogo", "campo_muestra", "seleccion_asignacion"],
            activo=True,
            deleted_at__isnull=True,
        ).exists():
            raise serializers.ValidationError({
                "criterio_limite_catalogo": "El catálogo seleccionado no es fuente de límite para esta prueba."
            })
        criterio_escala_item = attrs.get("criterio_limite_escala_item") or getattr(self.instance, "criterio_limite_escala_item", None)
        criterio_escala = attrs.get("criterio_limite_escala") or getattr(self.instance, "criterio_limite_escala", None)
        if criterio_escala_item and criterio_escala and criterio_escala_item.escala_id != criterio_escala.id:
            raise serializers.ValidationError({"criterio_limite_escala_item": "El criterio seleccionado no pertenece a la escala indicada."})
        if criterio_escala_item and not criterio_escala:
            criterio_escala = criterio_escala_item.escala
            attrs["criterio_limite_escala"] = criterio_escala
        global_scale_fields = PruebaLimiteCampo.objects.filter(
            fuente_limite__prueba=prueba,
            fuente_limite__tipo_limite="global",
            fuente_limite__activo=True,
            fuente_limite__deleted_at__isnull=True,
            tipo_comparacion__in=["escala", "escala_ordinal"],
            activo=True,
            deleted_at__isnull=True,
        ) if prueba else PruebaLimiteCampo.objects.none()
        if criterio_escala and not global_scale_fields.exists():
            # Multi-field/catalog contracts keep their ordinal values inside
            # criterio_limite_valor. A top-level scale copied by older builders
            # is redundant and must not prevent saving the reusable batch.
            criterio_escala = None
            criterio_escala_item = None
            attrs["criterio_limite_escala"] = None
            attrs["criterio_limite_escala_item"] = None
        elif criterio_escala and not global_scale_fields.filter(
            escala_comparacion=criterio_escala,
        ).exists():
            raise serializers.ValidationError({
                "criterio_limite_escala": "La escala seleccionada no corresponde a los campos de esta prueba."
            })
        if attrs.get("criterio_limite_valor") == "":
            attrs["criterio_limite_valor"] = None
        if not attrs.get("unidad"):
            attrs["unidad"] = getattr(prueba, "unidad_medida", None) or getattr(getattr(condicion, "unidad", None), "simbolo", None)
        return attrs


class LotePruebasPredefinidoSerializer(serializers.ModelSerializer):
    tipo_gestion_info = TipoGestionMuestraSerializer(source="tipo_gestion", read_only=True)
    detalles = LotePruebasPredefinidoDetalleSerializer(many=True, required=False)
    total_pruebas = serializers.SerializerMethodField()

    class Meta:
        model = LotePruebasPredefinido
        fields = [
            "id",
            "nombre",
            "descripcion",
            "tipo_lote",
            "tipo_gestion",
            "tipo_gestion_info",
            "es_default",
            "activo",
            "deleted_at",
            "created_at",
            "updated_at",
            "detalles",
            "total_pruebas",
        ]
        read_only_fields = ["deleted_at", "created_at", "updated_at", "total_pruebas", "tipo_gestion_info"]

    def get_total_pruebas(self, obj):
        return obj.detalles.filter(activo=True).count()

    def validate(self, attrs):
        tipo_lote = attrs.get("tipo_lote") or getattr(self.instance, "tipo_lote", "personalizado")
        tipo_gestion = attrs.get("tipo_gestion") if "tipo_gestion" in attrs else getattr(self.instance, "tipo_gestion", None)
        if tipo_lote == "gestion" and not tipo_gestion:
            raise serializers.ValidationError({"tipo_gestion": "Debe seleccionar un tipo de gestión."})
        return attrs

    def create(self, validated_data):
        detalles_data = validated_data.pop("detalles", [])
        instance = super().create(validated_data)
        self._replace_details(instance, detalles_data)
        self._apply_default_logic(instance)
        return instance

    def update(self, instance, validated_data):
        detalles_data = validated_data.pop("detalles", None)
        instance = super().update(instance, validated_data)
        if detalles_data is not None:
            self._replace_details(instance, detalles_data)
        self._apply_default_logic(instance)
        return instance

    def _replace_details(self, instance, detalles_data):
        instance.detalles.all().delete()
        for index, detail_data in enumerate(detalles_data, start=1):
            detail_data = dict(detail_data)
            orden = detail_data.pop("orden", None) or index
            LotePruebasPredefinidoDetalle.objects.create(
                lote=instance,
                orden=orden,
                **detail_data,
            )

    def _apply_default_logic(self, instance):
        if instance.es_default and instance.tipo_gestion_id:
            LotePruebasPredefinido.objects.filter(
                tipo_gestion=instance.tipo_gestion,
                es_default=True,
            ).exclude(pk=instance.pk).update(es_default=False)


class LotePruebasPredefinidoListSerializer(serializers.ModelSerializer):
    tipo_gestion_nombre = serializers.CharField(source="tipo_gestion.nombre", read_only=True)
    total_pruebas = serializers.SerializerMethodField()

    class Meta:
        model = LotePruebasPredefinido
        fields = [
            "id",
            "nombre",
            "tipo_lote",
            "tipo_gestion",
            "tipo_gestion_nombre",
            "es_default",
            "activo",
            "updated_at",
            "total_pruebas",
        ]

    def get_total_pruebas(self, obj):
        return obj.detalles.filter(activo=True).count()

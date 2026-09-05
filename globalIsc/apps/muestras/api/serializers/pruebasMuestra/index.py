import json

from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.muestras.api.models.muestras.index import Muestra
from apps.misc.api.models.lotesPruebasPredefinidos.index import LotePruebasPredefinido
from apps.misc.api.models.pruebas.index import Prueba
from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CatalogoTecnico,
    CatalogoTecnicoItem,
    EscalaComparacion,
    EscalaComparacionItem,
    CriterioEvaluacionLimite,
    PruebaFuenteLimite,
    PruebaLimiteCampo,
)
from apps.misc.api.models.technicalCatalogs.index import Condicion, EquipoPrueba, MetodoEquipo
from apps.misc.api.serializers.pruebas.index import PruebaDetailSerializer, format_condition_label
from apps.misc.api.serializers.technicalCatalogs.index import EquipoPruebaSerializer, MetodoEquipoSerializer
from apps.users.api.serializers.index import UserSerializer
from apps.muestras.api.services.limit_engine import resolve_and_evaluate_sample_test_result


class FlexibleCriterionValueField(serializers.Field):
    """Permite guardar criterios simples o mapas por campo."""

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
        text = str(value)
        try:
            return json.loads(text)
        except (TypeError, ValueError):
            return text


def _inherit_criterion_limit_value(attrs, criterion):
    """Use the configured criterion only when assignment sent no override."""
    if attrs.get("criterio_limite_valor") not in [None, ""]:
        return

    configured = criterion.valores_limite if isinstance(criterion.valores_limite, dict) else {}
    if configured:
        attrs["criterio_limite_valor"] = json.dumps(configured, ensure_ascii=False)
    elif criterion.valor not in [None, ""]:
        attrs["criterio_limite_valor"] = criterion.valor


def _has_catalog_limit_source(prueba):
    return bool(prueba) and PruebaFuenteLimite.objects.filter(
        prueba=prueba,
        tipo_limite__in=["catalogo", "campo_muestra", "seleccion_asignacion"],
        activo=True,
        deleted_at__isnull=True,
    ).exists()


def _discard_obsolete_catalog_selection(attrs):
    attrs["criterio_evaluacion"] = None
    attrs["criterio_limite_catalogo"] = None
    attrs["criterio_limite_item"] = None


class PruebaMuestraSerializer(serializers.ModelSerializer):
    prueba = PruebaDetailSerializer(read_only=True)
    usuario_solicitud = UserSerializer(read_only=True)
    usuario_medicion = UserSerializer(read_only=True)
    usuario_revision = UserSerializer(read_only=True)
    equipo_configurado_info = EquipoPruebaSerializer(source="equipo_configurado", read_only=True)
    metodo_configurado_info = MetodoEquipoSerializer(source="metodo_configurado", read_only=True)
    lote_id = serializers.CharField(source="muestra.lote_id", read_only=True)
    muestra_id = serializers.CharField(source="muestra.id", read_only=True)
    criterio_limite_catalogo_info = serializers.SerializerMethodField()
    criterio_limite_item_info = serializers.SerializerMethodField()
    criterio_limite_escala_info = serializers.SerializerMethodField()
    criterio_limite_escala_item_info = serializers.SerializerMethodField()
    criterio_evaluacion_info = serializers.SerializerMethodField()
    condicion_catalogo_info = serializers.SerializerMethodField()
    criterio_limite_valor = FlexibleCriterionValueField(required=False, allow_null=True)

    def get_condicion_catalogo_info(self, obj):
        if not obj.condicion_catalogo_id:
            return None
        condition = obj.condicion_catalogo
        return {
            "id": condition.id,
            "nombre": condition.nombre,
            "magnitud": condition.magnitud,
            "valor": str(condition.valor),
            "unidad": condition.unidad.simbolo,
        }

    def get_criterio_evaluacion_info(self, obj):
        if not obj.criterio_evaluacion_id:
            return None
        return {
            "id": obj.criterio_evaluacion_id,
            "nombre": obj.criterio_evaluacion.nombre,
            "codigo": obj.criterio_evaluacion.codigo,
            "tipo_criterio": obj.criterio_evaluacion.tipo_criterio,
            "fuente_limite": obj.criterio_evaluacion.fuente_limite_id,
        }

    def get_criterio_limite_catalogo_info(self, obj):
        if not obj.criterio_limite_catalogo_id:
            return None
        return {
            "id": obj.criterio_limite_catalogo_id,
            "nombre": obj.criterio_limite_catalogo.nombre,
            "codigo": obj.criterio_limite_catalogo.codigo,
        }

    def get_criterio_limite_item_info(self, obj):
        if not obj.criterio_limite_item_id:
            return None
        return {
            "id": obj.criterio_limite_item_id,
            "nombre": obj.criterio_limite_item.nombre,
            "codigo": obj.criterio_limite_item.codigo,
            "catalogo": obj.criterio_limite_item.catalogo_id,
        }

    def get_criterio_limite_escala_info(self, obj):
        if not obj.criterio_limite_escala_id:
            return None
        return {
            "id": obj.criterio_limite_escala_id,
            "nombre": obj.criterio_limite_escala.nombre,
            "codigo": obj.criterio_limite_escala.codigo,
        }

    def get_criterio_limite_escala_item_info(self, obj):
        if not obj.criterio_limite_escala_item_id:
            return None
        return {
            "id": obj.criterio_limite_escala_item_id,
            "etiqueta": obj.criterio_limite_escala_item.etiqueta,
            "orden": obj.criterio_limite_escala_item.orden,
            "escala": obj.criterio_limite_escala_item.escala_id,
        }

    class Meta:
        model = PruebaMuestra
        fields = "__all__"


class AssignmentTestSummarySerializer(serializers.ModelSerializer):
    """Small test representation used by the assignment workspace."""

    class Meta:
        model = Prueba
        fields = [
            "id",
            "nombre_variable",
            "acronimo",
            "condicion",
            "condicion_catalogo",
            "unidad_medida",
            "unidad_catalogo",
            "activo",
        ]


class PruebaMuestraAssignmentSerializer(PruebaMuestraSerializer):
    prueba = AssignmentTestSummarySerializer(read_only=True)

    class Meta(PruebaMuestraSerializer.Meta):
        pass


class CreatePruebaMuestraSerializer(serializers.ModelSerializer):
    criterio_limite_valor = FlexibleCriterionValueField(required=False, allow_null=True)
    condicion_catalogo = serializers.PrimaryKeyRelatedField(
        queryset=Condicion.objects.filter(activo=True),
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = PruebaMuestra
        fields = "__all__"
        read_only_fields = [
            "fecha_solicitud",
            "usuario_solicitud",
            "fecha_medicion",
            "fecha_revision",
            "evaluacion_limite",
            "estado_limite",
        ]

    def validate(self, attrs):
        prueba = attrs.get("prueba") or getattr(self.instance, "prueba", None)
        metodo = attrs.get("metodo_configurado") or getattr(self.instance, "metodo_configurado", None)
        equipo = attrs.get("equipo_configurado") or getattr(self.instance, "equipo_configurado", None)
        condicion = attrs.get("condicion_catalogo")

        if metodo and equipo and metodo.equipo_prueba_id != equipo.id:
            raise serializers.ValidationError({"metodo_configurado": "El método no pertenece al equipo seleccionado."})

        if not equipo and metodo:
            attrs["equipo_configurado"] = metodo.equipo_prueba

        if not attrs.get("condicion_configurada"):
            attrs["condicion_configurada"] = (
                format_condition_label(condicion)
                or getattr(prueba, "condicion", None)
                or None
            )
        if not attrs.get("unidad_configurada"):
            attrs["unidad_configurada"] = getattr(prueba, "unidad_medida", None) or None

        self._validate_limit_criterion(attrs, prueba)

        estado_asignacion = attrs.get("estado_asignacion") or getattr(self.instance, "estado_asignacion", "confirmada")
        if estado_asignacion == "confirmada":
            attrs["fecha_confirmacion"] = attrs.get("fecha_confirmacion") or getattr(self.instance, "fecha_confirmacion", None) or timezone.now()
        return attrs

    def create(self, validated_data):
        instance = super().create(validated_data)
        self._evaluate_limit(instance)
        return instance

    def update(self, instance, validated_data):
        instance = super().update(instance, validated_data)
        if "valor" in validated_data:
            self._evaluate_limit(instance)
        return instance

    @staticmethod
    def _evaluate_limit(instance):
        if instance.valor in [None, ""]:
            instance.evaluacion_limite = None
            instance.estado_limite = None
        else:
            evaluation = resolve_and_evaluate_sample_test_result(
                instance.valor,
                instance,
            )
            instance.evaluacion_limite = evaluation.to_dict()
            instance.estado_limite = evaluation.estado
        instance.save(update_fields=["evaluacion_limite", "estado_limite"])

    def _validate_limit_criterion(self, attrs, prueba):
        has_catalog_source = _has_catalog_limit_source(prueba)
        if not has_catalog_source:
            _discard_obsolete_catalog_selection(attrs)
        criterio_evaluacion = attrs.get("criterio_evaluacion") or getattr(self.instance, "criterio_evaluacion", None)
        if not has_catalog_source:
            criterio_evaluacion = None
        if not criterio_evaluacion and prueba and has_catalog_source:
            muestra = attrs.get("muestra") or getattr(self.instance, "muestra", None)
            source = PruebaFuenteLimite.objects.filter(
                prueba=prueba,
                activo=True,
                deleted_at__isnull=True,
                modo_seleccion="desde_muestra_editable",
            ).first()
            if source and muestra:
                selected_items = set(
                    muestra.atributos_tecnicos.filter(desconocido=False, item__isnull=False)
                    .values_list("item_id", flat=True)
                )
                for candidate in source.criterios.filter(activo=True, deleted_at__isnull=True).prefetch_related("selecciones_catalogo"):
                    required_items = set(candidate.selecciones_catalogo.values_list("item_id", flat=True))
                    if required_items and required_items.issubset(selected_items):
                        criterio_evaluacion = candidate
                        attrs["criterio_evaluacion"] = candidate
                        break
        if criterio_evaluacion:
            fuente = criterio_evaluacion.fuente_limite
            if prueba and fuente.prueba_id != prueba.id:
                raise serializers.ValidationError({"criterio_evaluacion": "El criterio no pertenece a la prueba seleccionada."})
            if criterio_evaluacion.catalogo_item_id:
                attrs["criterio_limite_item"] = criterio_evaluacion.catalogo_item
                attrs["criterio_limite_catalogo"] = criterio_evaluacion.catalogo_item.catalogo
            if criterio_evaluacion.escala_item_id:
                attrs["criterio_limite_escala_item"] = criterio_evaluacion.escala_item
                attrs["criterio_limite_escala"] = criterio_evaluacion.escala_item.escala
            _inherit_criterion_limit_value(attrs, criterio_evaluacion)

        criterio_item = attrs.get("criterio_limite_item") or getattr(self.instance, "criterio_limite_item", None)
        criterio_catalogo = attrs.get("criterio_limite_catalogo") or getattr(self.instance, "criterio_limite_catalogo", None)
        criterio_escala_item = attrs.get("criterio_limite_escala_item") or getattr(self.instance, "criterio_limite_escala_item", None)
        criterio_escala = attrs.get("criterio_limite_escala") or getattr(self.instance, "criterio_limite_escala", None)
        if not has_catalog_source:
            criterio_item = None
            criterio_catalogo = None
        if criterio_item and criterio_catalogo and criterio_item.catalogo_id != criterio_catalogo.id:
            raise serializers.ValidationError({"criterio_limite_item": "El criterio seleccionado no pertenece al catÃ¡logo indicado."})
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
                "criterio_limite_catalogo": "El catÃ¡logo seleccionado no es fuente de lÃ­mite para esta prueba."
            })
        if criterio_escala_item and criterio_escala and criterio_escala_item.escala_id != criterio_escala.id:
            raise serializers.ValidationError({"criterio_limite_escala_item": "El criterio seleccionado no pertenece a la escala indicada."})
        if criterio_escala_item and not criterio_escala:
            criterio_escala = criterio_escala_item.escala
            attrs["criterio_limite_escala"] = criterio_escala
        if criterio_escala and prueba and not _scale_limit_exists(prueba, criterio_escala) and criterio_catalogo:
            criterio_escala = None
            attrs["criterio_limite_escala"] = None
            attrs["criterio_limite_escala_item"] = None
        if criterio_escala and prueba and not _scale_limit_exists(prueba, criterio_escala):
            raise serializers.ValidationError({
                "criterio_limite_escala": "La escala seleccionada no es una fuente de limite global ordinal para esta prueba."
            })
        if attrs.get("criterio_limite_valor") == "":
            attrs["criterio_limite_valor"] = None


class BatchAssignPruebaItemSerializer(serializers.Serializer):
    prueba = serializers.PrimaryKeyRelatedField(queryset=Prueba.objects.filter(activo=True))
    equipo_prueba = serializers.PrimaryKeyRelatedField(queryset=EquipoPrueba.objects.filter(activo=True), required=False, allow_null=True)
    metodo_equipo = serializers.PrimaryKeyRelatedField(queryset=MetodoEquipo.objects.filter(activo=True), required=False, allow_null=True)
    condicion = serializers.PrimaryKeyRelatedField(queryset=Condicion.objects.filter(activo=True), required=False, allow_null=True)
    condicion_texto = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    unidad = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    configuracion_resultados = serializers.JSONField(required=False, default=dict)
    criterio_limite_catalogo = serializers.PrimaryKeyRelatedField(
        queryset=CatalogoTecnico.objects.filter(activo=True, deleted_at__isnull=True),
        required=False,
        allow_null=True,
    )
    criterio_evaluacion = serializers.PrimaryKeyRelatedField(
        queryset=CriterioEvaluacionLimite.objects.filter(activo=True, deleted_at__isnull=True),
        required=False,
        allow_null=True,
    )
    criterio_limite_item = serializers.PrimaryKeyRelatedField(
        queryset=CatalogoTecnicoItem.objects.filter(activo=True, deleted_at__isnull=True),
        required=False,
        allow_null=True,
    )
    criterio_limite_escala = serializers.PrimaryKeyRelatedField(
        queryset=EscalaComparacion.objects.filter(activo=True, deleted_at__isnull=True),
        required=False,
        allow_null=True,
    )
    criterio_limite_escala_item = serializers.PrimaryKeyRelatedField(
        queryset=EscalaComparacionItem.objects.filter(activo=True, deleted_at__isnull=True),
        required=False,
        allow_null=True,
    )
    criterio_limite_valor = FlexibleCriterionValueField(required=False, allow_null=True)

    def validate(self, attrs):
        prueba = attrs["prueba"]
        metodo = attrs.get("metodo_equipo")
        equipo = attrs.get("equipo_prueba") or (metodo.equipo_prueba if metodo else None)
        condicion = attrs.get("condicion") or getattr(prueba, "condicion_catalogo", None)

        if metodo and equipo and metodo.equipo_prueba_id != equipo.id:
            raise serializers.ValidationError({"metodo_equipo": "El método no pertenece al equipo seleccionado."})

        attrs["equipo_prueba"] = equipo
        attrs["metodo_equipo"] = metodo
        attrs["condicion"] = condicion
        attrs["condicion_texto"] = attrs.get("condicion_texto") or format_condition_label(condicion) or getattr(prueba, "condicion", None) or None
        has_catalog_source = _has_catalog_limit_source(prueba)
        if not has_catalog_source:
            _discard_obsolete_catalog_selection(attrs)
        criterio_evaluacion = attrs.get("criterio_evaluacion")
        if criterio_evaluacion:
            fuente = criterio_evaluacion.fuente_limite
            if fuente.prueba_id != prueba.id:
                raise serializers.ValidationError({"criterio_evaluacion": "El criterio no pertenece a la prueba seleccionada."})
            if criterio_evaluacion.catalogo_item_id:
                attrs["criterio_limite_item"] = criterio_evaluacion.catalogo_item
                attrs["criterio_limite_catalogo"] = criterio_evaluacion.catalogo_item.catalogo
            if criterio_evaluacion.escala_item_id:
                attrs["criterio_limite_escala_item"] = criterio_evaluacion.escala_item
                attrs["criterio_limite_escala"] = criterio_evaluacion.escala_item.escala
            _inherit_criterion_limit_value(attrs, criterio_evaluacion)
        criterio_item = attrs.get("criterio_limite_item")
        criterio_catalogo = attrs.get("criterio_limite_catalogo")
        if criterio_item and criterio_catalogo and criterio_item.catalogo_id != criterio_catalogo.id:
            raise serializers.ValidationError({"criterio_limite_item": "El criterio seleccionado no pertenece al catÃ¡logo indicado."})
        if criterio_item and not criterio_catalogo:
            criterio_catalogo = criterio_item.catalogo
            attrs["criterio_limite_catalogo"] = criterio_catalogo
        if criterio_catalogo and not PruebaFuenteLimite.objects.filter(
            prueba=prueba,
            catalogo_fuente=criterio_catalogo,
            tipo_limite__in=["catalogo", "campo_muestra", "seleccion_asignacion"],
            activo=True,
            deleted_at__isnull=True,
        ).exists():
            raise serializers.ValidationError({
                "criterio_limite_catalogo": "El catÃ¡logo seleccionado no es fuente de lÃ­mite para esta prueba."
            })
        criterio_escala_item = attrs.get("criterio_limite_escala_item")
        criterio_escala = attrs.get("criterio_limite_escala")
        if criterio_escala_item and criterio_escala and criterio_escala_item.escala_id != criterio_escala.id:
            raise serializers.ValidationError({"criterio_limite_escala_item": "El criterio seleccionado no pertenece a la escala indicada."})
        if criterio_escala_item and not criterio_escala:
            criterio_escala = criterio_escala_item.escala
            attrs["criterio_limite_escala"] = criterio_escala
        if criterio_escala and not _scale_limit_exists(prueba, criterio_escala) and criterio_catalogo:
            criterio_escala = None
            attrs["criterio_limite_escala"] = None
            attrs["criterio_limite_escala_item"] = None
        if criterio_escala and not _scale_limit_exists(prueba, criterio_escala):
            raise serializers.ValidationError({
                "criterio_limite_escala": "La escala seleccionada no es una fuente de limite global ordinal para esta prueba."
            })
        if attrs.get("criterio_limite_valor") == "":
            attrs["criterio_limite_valor"] = None
        missing_fields = _missing_manual_limit_fields(
            prueba,
            attrs.get("criterio_limite_valor"),
            bool(attrs.get("criterio_limite_escala_item")),
        )
        if missing_fields:
            raise serializers.ValidationError({
                "criterio_limite_valor": f"Complete el criterio de limite para: {', '.join(missing_fields)}."
            })
        attrs["unidad"] = attrs.get("unidad") or getattr(prueba, "unidad_medida", None) or None
        return attrs


class BatchAssignPruebasSerializer(serializers.Serializer):
    lote_id = serializers.CharField()
    sample_ids = serializers.ListField(child=serializers.CharField(), required=False, allow_empty=True)
    lote_predefinido = serializers.PrimaryKeyRelatedField(
        queryset=LotePruebasPredefinido.objects.filter(activo=True),
        required=False,
        allow_null=True,
    )
    estado_asignacion = serializers.ChoiceField(choices=[("borrador", "Borrador"), ("confirmada", "Confirmada")], default="borrador")
    pruebas = BatchAssignPruebaItemSerializer(many=True)

    def validate_pruebas(self, value):
        def comparable(item):
            normalized = {}
            for key, current in item.items():
                if hasattr(current, "pk"):
                    normalized[key] = current.pk
                elif isinstance(current, dict):
                    normalized[key] = json.dumps(current, sort_keys=True, default=str)
                else:
                    normalized[key] = current
            return normalized

        unique = []
        seen = {}
        for item in value:
            test_id = item["prueba"].pk
            if test_id not in seen:
                seen[test_id] = item
                unique.append(item)
                continue
            if comparable(seen[test_id]) != comparable(item):
                raise serializers.ValidationError(
                    "La misma prueba aparece con configuraciones diferentes. Deje una sola configuración."
                )
        return unique


def _scale_limit_exists(prueba, escala):
    if not prueba or not escala:
        return False
    return PruebaLimiteCampo.objects.filter(
        fuente_limite__prueba=prueba,
        fuente_limite__activo=True,
        fuente_limite__deleted_at__isnull=True,
        tipo_comparacion__in=["escala", "escala_ordinal"],
        escala_comparacion=escala,
        activo=True,
        deleted_at__isnull=True,
    ).exists()


def _configured_default_for_field(field):
    """Return the configured default for a limit field."""
    source = getattr(field, "fuente_limite", None)
    if source:
        criterion = source.criterios.filter(
            activo=True,
            deleted_at__isnull=True,
        ).order_by("id").first()
        if criterion:
            values = criterion.valores_limite if isinstance(criterion.valores_limite, dict) else {}
            value = values.get(str(field.id), values.get(field.codigo))
            if value not in [None, ""]:
                return value
    return field.valor_global


def _parsed_criterion_value(value):
    if value in [None, ""]:
        return None
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return value
    return value


def _has_assigned_value_for_field(parsed, field, *, allow_scalar=False):
    if parsed in [None, ""]:
        return False
    if isinstance(parsed, dict):
        nested = parsed.get("fields") if isinstance(parsed.get("fields"), dict) else None
        keys = [str(field.id), field.codigo, f"field_{field.id}"]
        for source in [parsed, nested]:
            if not source:
                continue
            if any(source.get(key) not in [None, ""] for key in keys if key):
                return True
        return False
    return bool(allow_scalar)


def _field_rule_config(field):
    source = getattr(field, "fuente_limite", None)
    config = getattr(source, "configuracion_regla", None) if source else None
    if not isinstance(config, dict):
        return {}
    fields = config.get("campos") if isinstance(config.get("campos"), list) else []
    for item in fields:
        if str(item.get("codigo") or "") == str(getattr(field, "codigo", "")):
            return item
        if (
            str(item.get("componente") or "") == str(getattr(field, "componente_id", "") or "")
            and str(item.get("resultado") or "") == str(getattr(field, "resultado_id", "") or "")
        ):
            return item
    return {}


def _field_origin(field):
    configured = _field_rule_config(field).get("origen_limite")
    if configured:
        return configured
    source = getattr(field, "fuente_limite", None)
    return "asignacion" if getattr(source, "tipo_limite", None) == "global" else "catalogo"


def _missing_manual_limit_fields(prueba, value, has_scale_item=False):
    fields = list(PruebaLimiteCampo.objects.filter(
        fuente_limite__prueba=prueba,
        fuente_limite__activo=True,
        fuente_limite__deleted_at__isnull=True,
        activo=True,
        deleted_at__isnull=True,
    ).exclude(
        operador="informativo",
    ).select_related("fuente_limite").prefetch_related("fuente_limite__criterios").order_by("orden", "id"))

    if not fields:
        return []

    fields = [field for field in fields if _field_origin(field) == "asignacion"]
    if not fields:
        return []

    scale_types = ["escala", "escala_ordinal"]
    parsed = _parsed_criterion_value(value)
    missing = []

    for field in fields:
        configured_default = _configured_default_for_field(field)
        has_default = configured_default not in [None, ""]
        is_scale = field.tipo_comparacion in scale_types

        if is_scale:
            has_override = bool(has_scale_item) or _has_assigned_value_for_field(parsed, field, allow_scalar=len(fields) == 1)
        else:
            has_override = _has_assigned_value_for_field(parsed, field, allow_scalar=len([item for item in fields if item.tipo_comparacion not in scale_types]) == 1)

        if not has_default and not has_override:
            missing.append(field.nombre)

    return missing

from django.db import transaction
from django.db.models import Max
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.text import slugify
from rest_framework import serializers

from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CatalogoTecnico,
    CatalogoTecnicoVersion,
    CampoTecnicoMuestra,
    CatalogoTecnicoCampo,
    CatalogoTecnicoItem,
    CatalogoTecnicoItemValor,
    EscalaComparacion,
    EscalaComparacionItem,
    normalize_scale_token,
    PruebaFuenteLimite,
    PruebaFuenteCatalogo,
    CriterioEvaluacionLimite,
    CriterioCatalogoSeleccion,
    PruebaLimiteCampo,
)
from apps.misc.api.serializers.pruebas.index import PruebaSerializer


def run_model_validation(instance, *, validate_unique=True):
    try:
        instance.full_clean(validate_unique=validate_unique)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.message_dict)


class CatalogoTecnicoCampoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CatalogoTecnicoCampo
        fields = "__all__"


class CatalogoTecnicoItemValorSerializer(serializers.ModelSerializer):
    campo_info = CatalogoTecnicoCampoSerializer(source="campo", read_only=True)

    class Meta:
        model = CatalogoTecnicoItemValor
        fields = "__all__"


class CatalogoTecnicoVersionSerializer(serializers.ModelSerializer):
    items_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CatalogoTecnicoVersion
        fields = "__all__"


class CatalogoTecnicoItemSerializer(serializers.ModelSerializer):
    valores = CatalogoTecnicoItemValorSerializer(many=True, required=False)

    class Meta:
        model = CatalogoTecnicoItem
        fields = "__all__"

    def validate_codigo(self, value):
        return slugify(value or "").replace("-", "_")

    def validate(self, attrs):
        version = attrs.get("version") or getattr(self.instance, "version", None)
        catalogo = attrs.get("catalogo") or getattr(self.instance, "catalogo", None)
        if version and catalogo and version.catalogo_id != catalogo.id:
            raise serializers.ValidationError({"version": "La versión debe pertenecer al catálogo seleccionado."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        valores_data = validated_data.pop("valores", [])
        item = CatalogoTecnicoItem.objects.create(**validated_data)
        for valor_data in valores_data:
            CatalogoTecnicoItemValor.objects.update_or_create(
                item=item,
                campo=valor_data["campo"],
                defaults={"valor": valor_data.get("valor")},
            )
        return item

    @transaction.atomic
    def update(self, instance, validated_data):
        valores_data = validated_data.pop("valores", None)
        instance = super().update(instance, validated_data)
        if valores_data is not None:
            for valor_data in valores_data:
                CatalogoTecnicoItemValor.objects.update_or_create(
                    item=instance,
                    campo=valor_data["campo"],
                    defaults={"valor": valor_data.get("valor")},
                )
        return instance


class CatalogoTecnicoSerializer(serializers.ModelSerializer):
    campos = CatalogoTecnicoCampoSerializer(many=True, read_only=True)
    items = CatalogoTecnicoItemSerializer(many=True, read_only=True)
    versiones = CatalogoTecnicoVersionSerializer(many=True, read_only=True)
    version_actual_info = CatalogoTecnicoVersionSerializer(source="version_actual", read_only=True)

    class Meta:
        model = CatalogoTecnico
        fields = "__all__"

    def validate_codigo(self, value):
        return slugify(value or "").replace("-", "_")


class CampoTecnicoMuestraSerializer(serializers.ModelSerializer):
    catalogo_info = CatalogoTecnicoSerializer(source="catalogo", read_only=True)

    class Meta:
        model = CampoTecnicoMuestra
        fields = "__all__"
        validators = []

    def validate_codigo(self, value):
        return slugify(value or "").replace("-", "_")

    def validate(self, attrs):
        instance = self.instance or CampoTecnicoMuestra()
        for field, value in attrs.items():
            setattr(instance, field, value)
        run_model_validation(instance)
        return attrs


class EscalaComparacionItemSerializer(serializers.ModelSerializer):
    valor_normalizado = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = EscalaComparacionItem
        fields = "__all__"
        validators = []

    def validate_valor_normalizado(self, value):
        return normalize_scale_token(value)

    def validate(self, attrs):
        etiqueta = attrs.get("etiqueta") or getattr(self.instance, "etiqueta", "")
        normalized = attrs.get("valor_normalizado") or etiqueta
        attrs["valor_normalizado"] = normalize_scale_token(normalized)
        if not attrs["valor_normalizado"]:
            raise serializers.ValidationError({"etiqueta": "Ingrese una etiqueta valida."})

        orden = attrs.get("orden")
        if orden is not None and int(orden) <= 0:
            raise serializers.ValidationError({"orden": "El orden debe ser mayor que cero."})

        numero_base = attrs.get("numero_base")
        if numero_base is not None and numero_base < 0:
            raise serializers.ValidationError({"numero_base": "El numero base no puede ser negativo."})
        return attrs

    def _next_order(self, escala):
        max_order = EscalaComparacionItem._base_manager.filter(
            escala=escala,
            deleted_at__isnull=True,
        ).aggregate(max_order=Max("orden"))["max_order"]
        return (max_order or 0) + 1

    @transaction.atomic
    def create(self, validated_data):
        escala = validated_data["escala"]
        normalized = validated_data["valor_normalizado"]
        if not validated_data.get("orden"):
            validated_data["orden"] = self._next_order(escala)

        existing = EscalaComparacionItem._base_manager.filter(
            escala=escala,
            valor_normalizado=normalized,
        ).first()
        if existing and existing.deleted_at is None:
            raise serializers.ValidationError({
                "valor_normalizado": "Ya existe un item activo con ese valor en esta escala."
            })
        if existing:
            for field, value in validated_data.items():
                setattr(existing, field, value)
            existing.activo = True
            existing.deleted_at = None
            existing.save()
            return existing
        return EscalaComparacionItem.objects.create(**validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        escala = validated_data.get("escala", instance.escala)
        normalized = validated_data.get("valor_normalizado", instance.valor_normalizado)
        duplicate = EscalaComparacionItem._base_manager.filter(
            escala=escala,
            valor_normalizado=normalized,
        ).exclude(pk=instance.pk).first()
        if duplicate and duplicate.deleted_at is None:
            raise serializers.ValidationError({
                "valor_normalizado": "Ya existe un item activo con ese valor en esta escala."
            })
        if duplicate:
            duplicate.soft_delete()

        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.deleted_at = None
        instance.activo = True
        instance.save()
        return instance


class EscalaComparacionSerializer(serializers.ModelSerializer):
    items = EscalaComparacionItemSerializer(many=True, read_only=True)

    class Meta:
        model = EscalaComparacion
        fields = "__all__"
        extra_kwargs = {"codigo": {"required": False, "allow_blank": True}}

    def validate_codigo(self, value):
        return slugify(value or "").replace("-", "_")


class PruebaLimiteCampoSerializer(serializers.ModelSerializer):
    operador = serializers.CharField()
    resultado_nombre = serializers.CharField(source="resultado.nombre", read_only=True)
    division_nombre = serializers.CharField(source="division.nombre", read_only=True)
    componente_nombre = serializers.CharField(source="componente.nombre", read_only=True)
    resultado_info = serializers.SerializerMethodField()
    division_info = serializers.SerializerMethodField()
    componente_info = serializers.SerializerMethodField()
    etiqueta_verdadero = serializers.SerializerMethodField()
    etiqueta_falso = serializers.SerializerMethodField()
    opciones_booleanas = serializers.SerializerMethodField()

    class Meta:
        model = PruebaLimiteCampo
        fields = "__all__"

    def get_resultado_info(self, obj):
        if not obj.resultado_id:
            return None
        return {
            "id": obj.resultado_id,
            "nombre": obj.resultado.nombre,
            "acronimo": getattr(obj.resultado, "acronimo", None),
        }

    def get_division_info(self, obj):
        if not obj.division_id:
            return None
        return {
            "id": obj.division_id,
            "nombre": obj.division.nombre,
            "orden": getattr(obj.division, "orden", None),
        }

    def get_componente_info(self, obj):
        if not obj.componente_id:
            return None
        return {
            "id": obj.componente_id,
            "nombre": obj.componente.nombre,
            "acronimo": getattr(obj.componente, "acronimo", None),
            "tipo_dato": getattr(obj.componente, "tipo_dato", None),
            "unidad_medida": getattr(obj.resultado, "unidad_medida", None),
            "etiqueta_verdadero": getattr(obj.componente, "etiqueta_verdadero", None) or "Sí",
            "etiqueta_falso": getattr(obj.componente, "etiqueta_falso", None) or "No",
        }

    def _boolean_labels(self, obj):
        component = getattr(obj, "componente", None)
        return (
            getattr(component, "etiqueta_verdadero", None) or "Sí",
            getattr(component, "etiqueta_falso", None) or "No",
        )

    def get_etiqueta_verdadero(self, obj):
        return self._boolean_labels(obj)[0]

    def get_etiqueta_falso(self, obj):
        return self._boolean_labels(obj)[1]

    def get_opciones_booleanas(self, obj):
        true_label, false_label = self._boolean_labels(obj)
        return [
            {"value": "true", "label": true_label},
            {"value": "false", "label": false_label},
        ]

    def validate_codigo(self, value):
        return slugify(value or "").replace("-", "_")

    def validate_operador(self, value):
        aliases = {
            "<=": "max",
            ">=": "min",
            "=": "eq",
            "menor_igual": "max",
            "mayor_igual": "min",
            "igual": "eq",
            "diferente": "neq",
            "en_lista": "in",
            "no_en_lista": "not_in",
            "escala_menor_igual": "scale_max",
            "escala_mayor_igual": "scale_min",
            "solo_informativo": "informativo",
        }
        value = aliases.get(value, value)
        valid = {choice for choice, _ in PruebaLimiteCampo.OPERADOR_CHOICES}
        if value not in valid:
            raise serializers.ValidationError("Operador no soportado.")
        return value

    def validate(self, attrs):
        instance = self.instance or PruebaLimiteCampo()
        for field, value in attrs.items():
            setattr(instance, field, value)
        run_model_validation(instance)
        return attrs


class CriterioEvaluacionLimiteSerializer(serializers.ModelSerializer):
    fuente_info = serializers.SerializerMethodField()
    catalogo_item_info = CatalogoTecnicoItemSerializer(source="catalogo_item", read_only=True)
    escala_item_info = EscalaComparacionItemSerializer(source="escala_item", read_only=True)
    selecciones_catalogo = serializers.SerializerMethodField()

    class Meta:
        model = CriterioEvaluacionLimite
        fields = "__all__"
        validators = []

    def get_fuente_info(self, obj):
        fuente = obj.fuente_limite
        return {
            "id": fuente.id,
            "tipo_limite": fuente.tipo_limite,
            "prueba": fuente.prueba_id,
            "prueba_nombre": getattr(fuente.prueba, "nombre_variable", None),
            "catalogo": fuente.catalogo_fuente_id,
            "campo_tecnico_muestra": fuente.campo_tecnico_muestra_id,
        }

    def get_selecciones_catalogo(self, obj):
        return [
            {
                "id": selection.id,
                "catalogo": selection.catalogo_id,
                "catalogo_nombre": selection.catalogo.nombre,
                "item": selection.item_id,
                "item_nombre": selection.item.nombre,
            }
            for selection in obj.selecciones_catalogo.select_related("catalogo", "item").all()
        ]

    def validate_codigo(self, value):
        return slugify(value or "").replace("-", "_")

    def validate(self, attrs):
        instance = self.instance or CriterioEvaluacionLimite()
        for field, value in attrs.items():
            setattr(instance, field, value)
        run_model_validation(instance)
        return attrs


class PruebaFuenteLimiteSerializer(serializers.ModelSerializer):
    prueba_info = PruebaSerializer(source="prueba", read_only=True)
    catalogo_info = CatalogoTecnicoSerializer(source="catalogo_fuente", read_only=True)
    campo_tecnico_info = CampoTecnicoMuestraSerializer(source="campo_tecnico_muestra", read_only=True)
    catalogo_resuelto = serializers.SerializerMethodField()
    campos_limite = PruebaLimiteCampoSerializer(many=True, read_only=True)
    criterios = CriterioEvaluacionLimiteSerializer(many=True, read_only=True)
    catalogos_configurados = serializers.SerializerMethodField()

    class Meta:
        model = PruebaFuenteLimite
        fields = "__all__"
        # Permite corregir/restaurar una asociación prueba-catalogo existente
        # sin que DRF detenga el POST por unique_together antes del ViewSet.
        validators = []

    def get_catalogo_resuelto(self, obj):
        catalog = obj.catalogo_fuente
        if not catalog and obj.campo_tecnico_muestra_id:
            catalog = obj.campo_tecnico_muestra.catalogo
        if not catalog:
            return None
        return {
            "id": catalog.id,
            "nombre": catalog.nombre,
            "codigo": catalog.codigo,
            "tipo_muestra": catalog.tipo_muestra,
        }

    def get_catalogos_configurados(self, obj):
        return [
            {
                "id": relation.id,
                "catalogo": relation.catalogo_id,
                "catalogo_nombre": relation.catalogo.nombre,
                "campo_tecnico_muestra": relation.campo_tecnico_muestra_id,
                "campo_tecnico_nombre": getattr(relation.campo_tecnico_muestra, "nombre_visible", None),
                "orden": relation.orden,
            }
            for relation in obj.catalogos_configurados.select_related(
                "catalogo", "campo_tecnico_muestra"
            ).filter(activo=True)
        ]

    def validate(self, attrs):
        instance = self.instance or PruebaFuenteLimite()
        for field, value in attrs.items():
            setattr(instance, field, value)
        run_model_validation(instance)
        return attrs

    def create(self, validated_data):
        prueba = validated_data.get("prueba")
        tipo_limite = validated_data.get("tipo_limite") or "catalogo"
        campo_tecnico = validated_data.get("campo_tecnico_muestra")
        if tipo_limite == "campo_muestra" and campo_tecnico:
            validated_data["catalogo_fuente"] = campo_tecnico.catalogo
        catalogo = validated_data.get("catalogo_fuente")
        if tipo_limite in ["global", "sin_limite"]:
            catalogo = None
            validated_data["catalogo_fuente"] = None
            validated_data["campo_tecnico_muestra"] = None
        if prueba and (catalogo or tipo_limite in ["global", "sin_limite"]):
            instance = (
                PruebaFuenteLimite.objects
                .filter(prueba=prueba, tipo_limite=tipo_limite, catalogo_fuente=catalogo)
                .order_by("id")
                .first()
            )
            if instance:
                for attr, value in validated_data.items():
                    setattr(instance, attr, value)
                instance.activo = True
                instance.deleted_at = None
                instance.save()
                return instance
        return super().create(validated_data)

    def update(self, instance, validated_data):
        tipo_limite = validated_data.get("tipo_limite", instance.tipo_limite)
        campo_tecnico = validated_data.get("campo_tecnico_muestra", instance.campo_tecnico_muestra)
        if tipo_limite == "campo_muestra" and campo_tecnico:
            validated_data["catalogo_fuente"] = campo_tecnico.catalogo
        if tipo_limite in ["global", "sin_limite"]:
            validated_data["catalogo_fuente"] = None
            validated_data["campo_tecnico_muestra"] = None
        return super().update(instance, validated_data)

    def validate(self, attrs):
        instance = self.instance or PruebaFuenteLimite()
        for field, value in attrs.items():
            setattr(instance, field, value)
        run_model_validation(instance)
        return attrs

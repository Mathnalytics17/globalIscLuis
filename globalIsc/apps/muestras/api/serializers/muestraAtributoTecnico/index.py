from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CatalogoTecnico,
    CatalogoTecnicoItem,
    CampoTecnicoMuestra,
)
from apps.muestras.api.models.muestraAtributoTecnico.index import MuestraAtributoTecnico
from apps.muestras.api.models.muestras.index import Muestra


class MuestraAtributoTecnicoSerializer(serializers.ModelSerializer):
    muestra = serializers.PrimaryKeyRelatedField(
        queryset=Muestra.objects.all(),
        required=False,
    )
    catalogo = serializers.PrimaryKeyRelatedField(
        queryset=CatalogoTecnico.objects.all(),
        required=False,
    )
    campo_tecnico = serializers.PrimaryKeyRelatedField(
        queryset=CampoTecnicoMuestra.objects.all(),
        required=False,
        allow_null=True,
    )
    catalogo_nombre = serializers.CharField(source="catalogo.nombre", read_only=True)
    catalogo_codigo = serializers.CharField(source="catalogo.codigo", read_only=True)
    campo_tecnico_nombre = serializers.CharField(source="campo_tecnico.nombre_visible", read_only=True)
    campo_tecnico_codigo = serializers.CharField(source="campo_tecnico.codigo", read_only=True)
    item_nombre = serializers.CharField(source="item.nombre", read_only=True)

    class Meta:
        model = MuestraAtributoTecnico
        fields = "__all__"
        read_only_fields = ["created_at", "updated_at"]
        validators = []

    def validate(self, attrs):
        campo_tecnico = attrs.get("campo_tecnico") or getattr(self.instance, "campo_tecnico", None)
        if campo_tecnico:
            attrs["catalogo"] = campo_tecnico.catalogo
        if not attrs.get("catalogo") and not getattr(self.instance, "catalogo", None):
            raise serializers.ValidationError({
                "catalogo": "Seleccione catalogo o campo tecnico."
            })
        instance = self.instance or MuestraAtributoTecnico(
            muestra=self.context.get("muestra")
        )
        for field, value in attrs.items():
            setattr(instance, field, value)
        try:
            instance.full_clean(exclude=["muestra"] if not instance.muestra_id else None)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        return attrs


def validate_required_sample_attributes(tipo_muestra, atributos_data):
    required_fields = CampoTecnicoMuestra.objects.filter(
        activo=True,
        deleted_at__isnull=True,
        obligatorio=True,
        visible_en_ingreso=True,
        tipo_muestra__in=[tipo_muestra, "ambos"],
        catalogo__tipo_muestra__in=[tipo_muestra, "ambos"],
    )

    if required_fields.exists():
        received_field_ids = {
            attribute.get("campo_tecnico").id
            for attribute in atributos_data
            if attribute.get("campo_tecnico")
        }
        missing = [
            field.nombre_visible
            for field in required_fields
            if field.id not in received_field_ids
        ]
        if missing:
            raise serializers.ValidationError({
                "atributos_tecnicos": f"Faltan campos tecnicos requeridos: {', '.join(missing)}."
            })
        return

    # El modelo nuevo ya no usa catálogos con nombres/códigos mágicos como regla
    # de obligatoriedad. Si no hay CampoTecnicoMuestra configurado para el tipo
    # de muestra, no se bloquea el registro por banderas viejas de catálogo.
    return


def replace_sample_attributes(muestra, atributos_data):
    validate_required_sample_attributes(muestra.tipo_muestra, atributos_data)
    sent_catalog_ids = []
    sent_field_ids = []
    for attribute_data in atributos_data:
        campo_tecnico = attribute_data.get("campo_tecnico")
        if campo_tecnico:
            attribute_data["catalogo"] = campo_tecnico.catalogo
        catalogo = attribute_data["catalogo"]
        item = attribute_data.get("item")
        if item and item.catalogo_id != catalogo.id:
            raise serializers.ValidationError({
                "atributos_tecnicos": "El item debe pertenecer al catalogo indicado."
            })
        lookup = {"muestra": muestra}
        if campo_tecnico:
            lookup["campo_tecnico"] = campo_tecnico
        else:
            lookup["catalogo"] = catalogo
        attribute, _ = MuestraAtributoTecnico.objects.update_or_create(
            **lookup,
            defaults={
                "catalogo": catalogo,
                "campo_tecnico": campo_tecnico,
                "item": item,
                "desconocido": attribute_data.get("desconocido", False),
                "observacion": attribute_data.get("observacion"),
            },
        )
        try:
            attribute.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict)
        sent_catalog_ids.append(catalogo.id)
        if campo_tecnico:
            sent_field_ids.append(campo_tecnico.id)

    if sent_field_ids:
        muestra.atributos_tecnicos.exclude(campo_tecnico_id__in=sent_field_ids).delete()
    else:
        muestra.atributos_tecnicos.exclude(catalogo_id__in=sent_catalog_ids).delete()

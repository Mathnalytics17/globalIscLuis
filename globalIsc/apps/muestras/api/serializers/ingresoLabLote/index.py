from django.db import transaction
from rest_framework import serializers

from apps.muestras.api.models.ingresoLabLote.index import IngresoLabLote
from apps.muestras.api.models.loteMuestras.index import LoteMuestras


class LabSampleMiniSerializer(serializers.Serializer):
    id = serializers.CharField()
    tipo_muestra = serializers.CharField()
    condicion = serializers.CharField()
    fecha_toma = serializers.DateTimeField(required=False, allow_null=True)
    referencia_marca = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    equipo_placa = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    referencia_equipo_nombre = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    fabricante = serializers.CharField(required=False, allow_null=True, allow_blank=True)
    is_ingresado = serializers.BooleanField()
    atributos_tecnicos = serializers.ListField(required=False)


class LoteDisponibleLaboratorioSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.SerializerMethodField()
    total_muestras = serializers.SerializerMethodField()
    muestras_aceite = serializers.SerializerMethodField()
    muestras_grasa = serializers.SerializerMethodField()
    muestras_ingresadas = serializers.SerializerMethodField()
    tipo_gestion_nombre = serializers.SerializerMethodField()
    puede_ingresar = serializers.SerializerMethodField()
    muestras_resumen = serializers.SerializerMethodField()

    class Meta:
        model = LoteMuestras
        fields = [
            "id",
            "tipo_cliente",
            "cliente_nombre",
            "contacto_nombre",
            "contacto_telefono",
            "contacto_email",
            "fecha_envio",
            "fecha_recepcion",
            "estado",
            "tipo_gestion",
            "tipo_gestion_nombre",
            "total_muestras",
            "muestras_aceite",
            "muestras_grasa",
            "muestras_ingresadas",
            "puede_ingresar",
            "muestras_resumen",
        ]

    def get_cliente_nombre(self, obj):
        if obj.tipo_cliente == "ocasional":
            return obj.cliente_ocasional_nombre or "Cliente ocasional"
        return getattr(obj.cliente_empresa, "nombre", None) or "Cliente registrado"

    def get_tipo_gestion_nombre(self, obj):
        return getattr(obj.tipo_gestion, "nombre", None)

    def get_total_muestras(self, obj):
        annotated = getattr(obj, "total_muestras_db", None)
        if annotated is not None:
            return annotated
        return obj.muestras.count()

    def get_muestras_aceite(self, obj):
        annotated = getattr(obj, "muestras_aceite_db", None)
        if annotated is not None:
            return annotated
        return obj.muestras.filter(tipo_muestra="aceite").count()

    def get_muestras_grasa(self, obj):
        annotated = getattr(obj, "muestras_grasa_db", None)
        if annotated is not None:
            return annotated
        return obj.muestras.filter(tipo_muestra="grasa").count()

    def get_muestras_ingresadas(self, obj):
        annotated = getattr(obj, "muestras_ingresadas_db", None)
        if annotated is not None:
            return annotated
        return obj.muestras.filter(is_ingresado=True).count()

    def get_puede_ingresar(self, obj):
        if hasattr(obj, "ingreso_lab_lote"):
            return False
        return self.get_total_muestras(obj) > 0 and obj.estado not in [
            "cancelado",
            "reportado",
            "en_laboratorio",
            "en_analisis",
            "parcial",
            "resultados_completos",
            "revisado",
        ]

    def get_muestras_resumen(self, obj):
        muestras = []
        for muestra in obj.muestras.all().order_by("id"):
            equipo = getattr(muestra, "referencia_equipo", None)
            campos_adicionales = muestra.campos_adicionales or {}
            atributos = []

            for atributo in muestra.atributos_tecnicos.all():
                catalogo = getattr(atributo, "catalogo", None)
                item = getattr(atributo, "item", None)
                atributos.append({
                    "catalogo": getattr(catalogo, "id", None),
                    "catalogo_codigo": getattr(catalogo, "codigo", None),
                    "catalogo_nombre": getattr(catalogo, "nombre", None),
                    "item": getattr(item, "id", None),
                    "item_nombre": getattr(item, "nombre", None),
                    "desconocido": atributo.desconocido,
                    "observacion": atributo.observacion,
                })

            muestras.append({
                "id": muestra.id,
                "tipo_muestra": muestra.tipo_muestra,
                "condicion": muestra.condicion,
                "fecha_toma": muestra.fecha_toma,
                "referencia_marca": muestra.referencia_marca,
                "equipo_placa": muestra.equipo_placa,
                "referencia_equipo_nombre": getattr(equipo, "nombre", None),
                "fabricante": campos_adicionales.get("fabricante"),
                "is_ingresado": muestra.is_ingresado,
                "atributos_tecnicos": atributos,
            })

        return muestras


class IngresoLabLoteSerializer(serializers.ModelSerializer):
    lote_info = LoteDisponibleLaboratorioSerializer(source="lote", read_only=True)
    usuario_recepcion_nombre = serializers.SerializerMethodField()

    class Meta:
        model = IngresoLabLote
        fields = [
            "id",
            "lote",
            "lote_info",
            "fecha_recepcion",
            "usuario_recepcion",
            "usuario_recepcion_nombre",
            "condiciones_entrega",
            "observaciones",
            "campos_adicionales",
            "fecha_registro",
        ]
        read_only_fields = ["usuario_recepcion", "fecha_registro"]

    def get_usuario_recepcion_nombre(self, obj):
        user = obj.usuario_recepcion
        full_name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
        return full_name or getattr(user, "email", None) or getattr(user, "username", "")


class CreateIngresoLabLoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngresoLabLote
        fields = [
            "lote",
            "fecha_recepcion",
            "condiciones_entrega",
            "observaciones",
            "campos_adicionales",
        ]

    def validate_lote(self, lote):
        if hasattr(lote, "ingreso_lab_lote"):
            raise serializers.ValidationError("Este lote ya fue ingresado al laboratorio.")

        if not lote.muestras.exists():
            raise serializers.ValidationError("Este lote no tiene muestras asociadas.")

        if lote.estado in ["cancelado", "reportado", "en_laboratorio", "en_analisis", "parcial", "resultados_completos", "revisado"]:
            raise serializers.ValidationError("Este lote no puede ingresarse al laboratorio por su estado actual.")

        return lote

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get("request")
        lote = validated_data["lote"]

        ingreso = IngresoLabLote.objects.create(
            usuario_recepcion=request.user,
            **validated_data,
        )

        lote.muestras.update(is_ingresado=True)
        lote.estado = "en_laboratorio"
        if ingreso.fecha_recepcion:
            lote.fecha_recepcion = ingreso.fecha_recepcion.date()
            lote.save(update_fields=["estado", "fecha_recepcion", "fecha_actualizacion"])
        else:
            lote.save(update_fields=["estado", "fecha_actualizacion"])

        return ingreso

from rest_framework import serializers

from apps.reporte.api.models.index import Reporte, ReporteEnvio


def _user_name(user):
    if not user:
        return None
    full_name = f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}".strip()
    return full_name or getattr(user, "email", None) or str(user)


class ReporteEnvioSerializer(serializers.ModelSerializer):
    enviado_por_nombre = serializers.SerializerMethodField()
    destinatario_usuario_nombre = serializers.SerializerMethodField()

    class Meta:
        model = ReporteEnvio
        fields = "__all__"

    def get_enviado_por_nombre(self, obj):
        return _user_name(obj.enviado_por)

    def get_destinatario_usuario_nombre(self, obj):
        return _user_name(obj.destinatario_usuario)


class ReporteSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.SerializerMethodField()
    lote_id = serializers.CharField(source="lote.id", read_only=True)
    muestra_id = serializers.CharField(source="muestra.id", read_only=True)
    generado_por = serializers.SerializerMethodField()
    enviado_por = serializers.SerializerMethodField()
    envios = ReporteEnvioSerializer(many=True, read_only=True)
    ultima_version = serializers.SerializerMethodField()

    class Meta:
        model = Reporte
        fields = "__all__"

    def get_empresa_nombre(self, obj):
        lote = obj.lote or getattr(obj.muestra, "lote", None)
        empresa = getattr(lote, "cliente_empresa", None)
        return getattr(empresa, "nombre", None) or getattr(lote, "cliente_ocasional_nombre", None)

    def get_generado_por(self, obj):
        return _user_name(obj.usuario_emision)

    def get_enviado_por(self, obj):
        return _user_name(obj.usuario_envio)

    def get_ultima_version(self, obj):
        annotated = getattr(obj, "ultima_version_value", None)
        if annotated is not None:
            return annotated
        return (
            Reporte.objects
            .filter(muestra_id=obj.muestra_id)
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
        ) or obj.version


class ReporteSummarySerializer(serializers.ModelSerializer):
    """Read model for report listings.

    A report snapshot can contain the complete interpretation and every result
    of a sample. Returning it from dashboard/list screens made a small report
    library transfer megabytes of JSON although the UI only needs metadata.
    """

    empresa_nombre = serializers.SerializerMethodField()
    lote_id = serializers.CharField(source="lote.id", read_only=True)
    muestra_id = serializers.CharField(source="muestra.id", read_only=True)
    generado_por = serializers.SerializerMethodField()
    enviado_por = serializers.SerializerMethodField()
    ultima_version = serializers.IntegerField(
        source="ultima_version_value", read_only=True
    )

    class Meta:
        model = Reporte
        fields = [
            "id",
            "consecutivo",
            "empresa_nombre",
            "lote_id",
            "muestra_id",
            "version",
            "ultima_version",
            "fecha_emision",
            "fecha_generacion",
            "fecha_envio",
            "fecha_aprobacion",
            "estatus",
            "visible_cliente",
            "generado_por",
            "enviado_por",
            "ruta_archivo",
            "with_limites",
        ]

    def get_empresa_nombre(self, obj):
        lote = obj.lote or getattr(obj.muestra, "lote", None)
        empresa = getattr(lote, "cliente_empresa", None)
        return getattr(empresa, "nombre", None) or getattr(
            lote, "cliente_ocasional_nombre", None
        )

    def get_generado_por(self, obj):
        return _user_name(obj.usuario_emision)

    def get_enviado_por(self, obj):
        return _user_name(obj.usuario_envio)


class CreateReporteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reporte
        fields = "__all__"
        read_only_fields = [
            "consecutivo",
            "usuario_emision",
            "usuario_envio",
            "fecha_emision",
            "fecha_generacion",
            "fecha_envio",
            "version",
            "snapshot",
        ]

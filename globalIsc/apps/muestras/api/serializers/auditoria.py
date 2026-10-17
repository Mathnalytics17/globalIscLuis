from rest_framework import serializers

from apps.muestras.api.models.auditoria import EventoAuditoriaOperativa
from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CatalogoTecnicoVersion,
    PruebaFuenteLimite,
)
from apps.misc.api.serializers.dynamicTechnicalConfig.index import (
    CatalogoTecnicoVersionSerializer,
    PruebaFuenteLimiteSerializer,
)


class EventoAuditoriaOperativaSerializer(serializers.ModelSerializer):
    actor_nombre = serializers.SerializerMethodField()
    empresa_nombre = serializers.CharField(source="empresa.nombre", read_only=True)
    lote_codigo = serializers.CharField(source="lote.id", read_only=True)
    muestra_codigo = serializers.CharField(source="muestra.id", read_only=True)
    maquina_nombre = serializers.CharField(source="maquina.nombre", read_only=True)
    punto_muestreo_nombre = serializers.CharField(source="punto_muestreo.nombre", read_only=True)
    estado_anterior = serializers.SerializerMethodField()

    class Meta:
        model = EventoAuditoriaOperativa
        fields = (
            "id", "creado_en", "actor", "actor_nombre", "empresa", "empresa_nombre", "lote", "lote_codigo",
            "muestra", "muestra_codigo", "prueba_muestra", "reporte", "maquina", "maquina_nombre", "punto_muestreo", "punto_muestreo_nombre",
            "tipo_entidad", "entidad_id", "entidad_etiqueta", "accion", "detalle",
            "motivo", "estado_anterior", "estado_nuevo", "metadata", "origen",
            "correlation_id",
        )

    def get_actor_nombre(self, obj):
        if not obj.actor:
            return "Sistema"
        return obj.actor.get_full_name() or obj.actor.email or str(obj.actor_id)

    def get_estado_anterior(self, obj):
        """Recover lineage for configuration events created before it was saved.

        The first released version of the limits workflow recorded a valid
        creation event but did not include its base snapshot.  The version is
        still recoverable from its immutable predecessors, so expose it here
        rather than leaving a misleading empty "Antes" panel.
        """
        if obj.estado_anterior:
            return obj.estado_anterior
        try:
            if obj.accion == "limites.version_creada":
                source = PruebaFuenteLimite.objects.filter(pk=obj.entidad_id).first()
                if source:
                    previous = PruebaFuenteLimite.objects.filter(
                        prueba_id=source.prueba_id,
                        version__lt=source.version,
                    ).order_by("-version", "-id").first()
                    if previous:
                        return PruebaFuenteLimiteSerializer(previous).data
            if obj.accion == "catalogos.version_creada":
                version = CatalogoTecnicoVersion.objects.filter(pk=obj.entidad_id).first()
                if version:
                    previous = CatalogoTecnicoVersion.objects.filter(
                        catalogo_id=version.catalogo_id,
                        numero__lt=version.numero,
                    ).order_by("-numero", "-id").first()
                    if previous:
                        return CatalogoTecnicoVersionSerializer(previous).data
        except Exception:
            # Traceability must remain readable even if a historical record was
            # purged independently from the technical configuration.
            pass
        return {}

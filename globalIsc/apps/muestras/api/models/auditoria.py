from django.db import models


class EventoAuditoriaOperativa(models.Model):
    """Registro inmutable de eventos relevantes del flujo de laboratorio.

    Los historiales especializados (resultado, muestra y reporte) conservan el
    detalle propio de su dominio. Esta entidad les da una cronología común para
    investigar un lote o una muestra sin tener que recorrer varias pantallas.
    """

    ORIGEN_CHOICES = [
        ("ui", "Interfaz"),
        ("api", "API"),
        ("importacion", "Importación"),
        ("proceso", "Proceso automático"),
        ("ia", "Asistente IA"),
    ]

    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)
    actor = models.ForeignKey(
        "users.User", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="eventos_operativos",
    )
    empresa = models.ForeignKey(
        "misc.Empresa", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="eventos_operativos",
    )
    lote = models.ForeignKey(
        "muestras.LoteMuestras", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="eventos_auditoria",
    )
    muestra = models.ForeignKey(
        "muestras.Muestra", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="eventos_auditoria",
    )
    prueba_muestra = models.ForeignKey(
        "muestras.PruebaMuestra", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="eventos_auditoria",
    )
    reporte = models.ForeignKey(
        "reporte.Reporte", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="eventos_auditoria",
    )
    maquina = models.ForeignKey(
        "activesTree.Maquina", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="eventos_auditoria",
    )
    punto_muestreo = models.ForeignKey(
        "activesTree.PuntoMuestreo", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="eventos_auditoria",
    )

    tipo_entidad = models.CharField(max_length=40, db_index=True)
    entidad_id = models.CharField(max_length=80, db_index=True)
    entidad_etiqueta = models.CharField(max_length=255, blank=True, default="")
    accion = models.CharField(max_length=100, db_index=True)
    detalle = models.TextField(blank=True, default="")
    motivo = models.TextField(blank=True, default="")
    estado_anterior = models.JSONField(default=dict, blank=True)
    estado_nuevo = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    origen = models.CharField(max_length=20, choices=ORIGEN_CHOICES, default="ui")
    correlation_id = models.CharField(max_length=64, blank=True, default="", db_index=True)

    class Meta:
        ordering = ["-creado_en", "-id"]
        indexes = [
            models.Index(fields=["empresa", "creado_en"], name="muestras_e_empresa_1cac08_idx"),
            models.Index(fields=["lote", "creado_en"], name="muestras_e_lote_id_845f3d_idx"),
            models.Index(fields=["muestra", "creado_en"], name="muestras_e_muestra__947b98_idx"),
            models.Index(fields=["maquina", "creado_en"], name="muestras_e_maquina__38cac3_idx"),
            models.Index(fields=["tipo_entidad", "entidad_id", "creado_en"], name="muestras_e_tipo_en_473424_idx"),
            models.Index(fields=["accion", "creado_en"], name="muestras_e_accion_9f27c5_idx"),
        ]

    def __str__(self):
        return f"{self.accion} · {self.tipo_entidad}:{self.entidad_id}"

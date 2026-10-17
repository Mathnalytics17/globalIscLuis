from django.db import models


class CorridaImportacion(models.Model):
    """Evidencia inmutable de una ejecución de importación masiva."""

    class Estado(models.TextChoices):
        BORRADOR = "borrador", "Borrador"
        VALIDADA = "validada", "Validada"
        APLICADA = "aplicada", "Aplicada"
        PARCIAL = "parcial", "Aplicada parcialmente"
        FALLIDA = "fallida", "Fallida"
        REVERTIDA = "revertida", "Revertida"

    creado_en = models.DateTimeField(auto_now_add=True)
    finalizado_en = models.DateTimeField(null=True, blank=True)
    empresa = models.ForeignKey("misc.Empresa", null=True, blank=True, on_delete=models.SET_NULL, related_name="corridas_importacion")
    actor = models.ForeignKey("users.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="corridas_importacion")
    tipo = models.CharField(max_length=60, default="migracion_historica")
    estado = models.CharField(max_length=16, choices=Estado.choices, default=Estado.BORRADOR)
    archivo_nombre = models.CharField(max_length=255, blank=True, default="")
    archivo_referencia = models.CharField(max_length=500, blank=True, default="")
    checksum = models.CharField(max_length=128, blank=True, default="")
    total_filas = models.PositiveIntegerField(default=0)
    creadas = models.PositiveIntegerField(default=0)
    actualizadas = models.PositiveIntegerField(default=0)
    omitidas = models.PositiveIntegerField(default=0)
    errores = models.PositiveIntegerField(default=0)
    advertencias = models.JSONField(default=list, blank=True)
    detalle_errores = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    reversible = models.BooleanField(default=False)
    revertida_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creado_en", "-id"]
        indexes = [models.Index(fields=["empresa", "creado_en"]), models.Index(fields=["estado", "creado_en"])]

    def __str__(self):
        return f"{self.tipo} · {self.archivo_nombre or self.pk}"

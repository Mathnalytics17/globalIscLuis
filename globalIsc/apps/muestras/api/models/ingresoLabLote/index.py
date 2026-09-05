from django.db import models
from apps.users.api.models.index import User
from apps.muestras.api.models.loteMuestras.index import LoteMuestras


class IngresoLabLote(models.Model):
    """
    Registro de ingreso al laboratorio a nivel de LOTE.

    Antes el ingreso era muestra por muestra. Ahora el lote contiene 1..N muestras,
    por eso el ingreso se registra una sola vez para el lote y se marcan todas sus
    muestras como ingresadas.
    """

    lote = models.OneToOneField(
        LoteMuestras,
        on_delete=models.CASCADE,
        related_name="ingreso_lab_lote",
    )
    fecha_recepcion = models.DateTimeField()
    usuario_recepcion = models.ForeignKey(User, on_delete=models.PROTECT)
    condiciones_entrega = models.TextField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    campos_adicionales = models.JSONField(blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha_recepcion"]
        indexes = [
            models.Index(fields=["lote"]),
            models.Index(fields=["fecha_recepcion"]),
            models.Index(fields=["usuario_recepcion"]),
        ]

    def __str__(self):
        return f"Ingreso laboratorio lote {self.lote_id}"

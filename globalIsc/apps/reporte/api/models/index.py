from django.db import models
from django.utils import timezone

from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.muestras.index import Muestra
from apps.users.api.models.index import User


class Reporte(models.Model):
    ESTATUS_CHOICES = [
        ("borrador", "Borrador"),
        ("pendiente_aprobacion", "Pendiente de aprobacion"),
        ("generado", "Generado"),
        ("aprobado", "Aprobado"),
        ("enviado", "Enviado"),
        ("anulado", "Anulado"),
    ]

    consecutivo = models.CharField(max_length=30, unique=True)
    muestra = models.ForeignKey(Muestra, on_delete=models.CASCADE, related_name="reportes")
    lote = models.ForeignKey(
        LoteMuestras,
        on_delete=models.CASCADE,
        related_name="reportes",
        blank=True,
        null=True,
    )
    version = models.PositiveIntegerField(default=1)
    snapshot = models.JSONField(blank=True, null=True)

    fecha_emision = models.DateTimeField()
    fecha_generacion = models.DateTimeField(blank=True, null=True)
    fecha_envio = models.DateTimeField(blank=True, null=True)

    usuario_emision = models.ForeignKey(User, on_delete=models.PROTECT, related_name="reportes_emitidos")
    usuario_aprobacion = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="reportes_aprobados",
        blank=True,
        null=True,
    )
    usuario_envio = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="reportes_enviados",
        blank=True,
        null=True,
    )
    fecha_aprobacion = models.DateTimeField(blank=True, null=True)

    comentarios = models.TextField(blank=True, null=True)
    conclusiones = models.TextField(blank=True, null=True)
    ruta_archivo = models.CharField(max_length=255, blank=True, null=True)
    estatus = models.CharField(max_length=30, choices=ESTATUS_CHOICES, default="generado")
    visible_cliente = models.BooleanField(default=False)
    notas_internas = models.TextField(blank=True, null=True)

    firma_ruta = models.TextField(blank=True, null=True)
    Responsable = models.CharField(max_length=255, blank=True, null=True)
    with_limites = models.BooleanField(default=True)

    class Meta:
        ordering = ["-fecha_emision", "-id"]
        unique_together = [("muestra", "version")]
        indexes = [
            models.Index(fields=["lote", "version"]),
            models.Index(fields=["estatus"]),
            models.Index(fields=["visible_cliente"]),
            models.Index(fields=["fecha_emision"]),
            models.Index(fields=["fecha_envio"]),
        ]

    def __str__(self):
        return f"{self.consecutivo} v{self.version}"

    def save(self, *args, **kwargs):
        if not self.lote_id and self.muestra_id:
            self.lote = self.muestra.lote

        if not self.fecha_generacion:
            self.fecha_generacion = self.fecha_emision or timezone.now()

        if not self.version and self.muestra_id:
            last_version = (
                Reporte.objects
                .filter(muestra_id=self.muestra_id)
                .order_by("-version")
                .values_list("version", flat=True)
                .first()
            )
            self.version = (last_version or 0) + 1

        if not self.consecutivo:
            year = timezone.now().year
            prefix = f"R{year}"
            last_reporte = (
                Reporte.objects
                .filter(consecutivo__startswith=prefix)
                .order_by("-id")
                .first()
            )
            last_num = 0
            if last_reporte and last_reporte.consecutivo:
                digits = "".join(ch for ch in last_reporte.consecutivo.replace(prefix, "") if ch.isdigit())
                last_num = int(digits or 0)
            self.consecutivo = f"{prefix}{str(last_num + 1).zfill(5)}"

        super().save(*args, **kwargs)


class ReporteEnvio(models.Model):
    CANAL_CHOICES = [
        ("email", "Email"),
        ("app", "Aplicacion"),
    ]

    ESTADO_CHOICES = [
        ("enviado", "Enviado"),
        ("fallido", "Fallido"),
    ]

    reporte = models.ForeignKey(Reporte, related_name="envios", on_delete=models.CASCADE)
    canal = models.CharField(max_length=20, choices=CANAL_CHOICES)
    destinatario_email = models.EmailField(blank=True, null=True)
    destinatario_usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="reportes_recibidos",
        blank=True,
        null=True,
    )
    enviado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="envios_reportes_realizados",
        blank=True,
        null=True,
    )
    fecha_envio = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="enviado")
    error = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-fecha_envio"]

    def __str__(self):
        return f"{self.reporte_id} - {self.canal} - {self.estado}"

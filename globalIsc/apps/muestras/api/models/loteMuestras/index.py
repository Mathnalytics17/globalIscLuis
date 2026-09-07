from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone

from apps.users.api.models.index import User


class LoteMuestras(models.Model):
    TIPO_CLIENTE_CHOICES = [
        ("registrado", "Cliente registrado"),
        ("ocasional", "Cliente ocasional"),
    ]

    TIPO_GESTION_CHOICES = [
        ("comercial", "comercial"),
        ("postventa", "postventa"),
        ("pqrs", "PQRS"),

    ]

    ESTADO_CHOICES = [
        ("borrador", "Borrador"),
        ("registrado", "Registrado"),
        ("recibido", "Recibido"),
        ("en_laboratorio", "En laboratorio"),
        ("en_analisis", "En análisis"),
        ("parcial", "Parcial"),
        ("resultados_completos", "Resultados completos"),
        ("revisado", "Revisado"),
        ("reportado", "Reportado"),
        ("cancelado", "Cancelado"),
    ]

    id = models.CharField(max_length=20, primary_key=True)

    tipo_cliente = models.CharField(
        max_length=20,
        choices=TIPO_CLIENTE_CHOICES,
        default="registrado",
    )

    # Para cliente registrado.
    # IMPORTANTE:
    # Cambia "companies.Company" por el app_label real de tu modelo de empresas.
    # Si tu modelo se llama Empresa, podría ser algo como "companies.Empresa".
    cliente_empresa = models.ForeignKey(
        "misc.Empresa",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="lotes_muestras",
    )

    # Para cliente ocasional.
    cliente_ocasional_nombre = models.CharField(max_length=150, blank=True, null=True)

    contacto_nombre = models.CharField(max_length=120, blank=True, null=True)
    contacto_telefono = models.CharField(max_length=50, blank=True, null=True)
    contacto_email = models.EmailField(blank=True, null=True)

    fecha_envio = models.DateField()
    fecha_recepcion = models.DateField(blank=True, null=True)

    tipo_gestion = models.ForeignKey(
        "misc.TipoGestionMuestra",
        on_delete=models.PROTECT,
        related_name="lotes_muestras",
        blank=True,
        null=True,
    )

    estado = models.CharField(
        max_length=30,
        choices=ESTADO_CHOICES,
        default="registrado",
    )

    observaciones = models.TextField(blank=True, null=True)
    motivo_cancelacion = models.TextField(blank=True, default="")
    fecha_cancelacion = models.DateTimeField(blank=True, null=True)
    cancelado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="lotes_cancelados",
        blank=True,
        null=True,
    )

    usuario_registro = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="lotes_muestras_registrados",
    )

    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-fecha_registro"]
        indexes = [
            models.Index(fields=["tipo_cliente"]),
            models.Index(fields=["estado"]),
            models.Index(fields=["fecha_envio"]),
            models.Index(fields=["tipo_gestion"]),
            models.Index(fields=["cliente_empresa", "fecha_envio"]),
        ]

    def __str__(self):
        return self.id

    def save(self, *args, **kwargs):
        if not self.id:
            year = timezone.now().year
            prefix = f"L{year}"

            last_lote = (
                LoteMuestras.objects
                .filter(id__startswith=prefix)
                .order_by("-id")
                .first()
            )

            if last_lote:
                last_num = int(last_lote.id.replace(prefix, ""))
                new_num = last_num + 1
            else:
                new_num = 1

            self.id = f"{prefix}{str(new_num).zfill(4)}"

        super().save(*args, **kwargs)

    @property
    def total_muestras(self):
        return self.muestras.count()

    @property
    def muestras_ingresadas(self):
        return self.muestras.filter(is_ingresado=True).count()

    @property
    def muestras_resultado_ingresado(self):
        return self.muestras.filter(is_resultado_ingresado=True).count()

    @property
    def muestras_revisadas(self):
        return self.muestras.filter(is_revisado=True).count()

    @property
    def progreso(self):
        muestras_activas = self.muestras.filter(estado_operativo="activa")
        total = muestras_activas.count()

        if total == 0:
            return {
                "total": 0,
                "procesadas": 0,
                "porcentaje": 0,
                "label": "0/0 procesadas",
            }

        procesadas = muestras_activas.filter(is_resultado_ingresado=True).count()
        porcentaje = round((procesadas / total) * 100)

        return {
            "total": total,
            "procesadas": procesadas,
            "porcentaje": porcentaje,
            "label": f"{procesadas}/{total} procesadas",
        }

    def recalcular_estado(self, save=True):
        muestras = self.muestras.filter(estado_operativo="activa")
        total = muestras.count()

        if self.estado == "cancelado":
            return self.estado

        if total == 0:
            nuevo_estado = "registrado" if self.muestras.exists() else "borrador"
        elif muestras.filter(is_revisado=True).count() == total:
            nuevo_estado = "revisado"
        elif muestras.filter(is_resultado_ingresado=True).count() == total:
            nuevo_estado = "resultados_completos"
        elif muestras.filter(is_resultado_ingresado=True).exists():
            nuevo_estado = "parcial"
        elif muestras.filter(is_ingresado=True).exists():
            nuevo_estado = "en_laboratorio"
        else:
            nuevo_estado = "registrado"

        self.estado = nuevo_estado

        if save:
            self.save(update_fields=["estado", "fecha_actualizacion"])

        return nuevo_estado

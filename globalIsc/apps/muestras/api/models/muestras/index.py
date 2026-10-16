from django.db import connection, models, transaction
from apps.users.api.models.index import User
from django.core.validators import MinValueValidator
import uuid
from apps.activesTree.api.models.machines.index import Maquina
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from django.utils import timezone
class Muestra(models.Model):
    ESTADO_OPERATIVO_CHOICES = [
        ("activa", "Activa"),
        ("invalidada", "Invalidada"),
    ]
    UNIDADES_PERIODO = [
        ('horas', 'Horas'),
        ('km', 'Kilómetros'),
        ('millas', 'Millas'),
        ('dias', 'Días'),
    ]

    TIPO_MUESTRA_CHOICES = [
        ("aceite", "Aceite"),
        ("grasa", "Grasa"),
    ]

    CONDICION_MUESTRA_CHOICES = [
        ("nueva", "Nueva"),
        ("usada", "Usada"),
    ]

    lote = models.ForeignKey(
        LoteMuestras,
        on_delete=models.CASCADE,
        related_name="muestras",
        blank=True,
        null=True,
    )

    tipo_muestra = models.CharField(
        max_length=20,
        choices=TIPO_MUESTRA_CHOICES,
        default="aceite",
    )

    id = models.CharField(max_length=20, primary_key=True)  # M20230001
    fecha_toma = models.DateTimeField()
    contacto_cliente = models.CharField(max_length=100, blank=True, null=True)
    equipo_placa = models.CharField(max_length=50, blank=True, null=True)
    referencia_equipo = models.ForeignKey(
    Maquina,
    on_delete=models.PROTECT,
    blank=True,
    null=True
)
    periodo_servicio_aceite = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    unidad_periodo_aceite = models.CharField(max_length=10, choices=UNIDADES_PERIODO, blank=True, null=True)
    periodo_servicio_equipo = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    unidad_periodo_equipo = models.CharField(max_length=10, choices=UNIDADES_PERIODO, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    campos_adicionales = models.JSONField(blank=True, null=True)
    estado_operativo = models.CharField(max_length=20, choices=ESTADO_OPERATIVO_CHOICES, default="activa", db_index=True)
    motivo_invalidacion = models.TextField(blank=True, default="")
    fecha_invalidacion = models.DateTimeField(blank=True, null=True)
    invalidada_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="muestras_invalidadas",
        blank=True,
        null=True,
    )
    usuario_registro = models.ForeignKey(User, on_delete=models.PROTECT)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    is_ingresado=models.BooleanField(default=False)
    is_revisado=models.BooleanField(default=False)
    is_resultado_ingresado=models.BooleanField(default=False)
    was_checked=models.DateField(default="2025-05-01")
    
    condicion = models.CharField(
        max_length=20,
        choices=CONDICION_MUESTRA_CHOICES,
        default="usada",
    )

    fecha_envio = models.DateField(blank=True, null=True)

    # Histórico opcional. Ya no es obligatorio en el nuevo flujo.
    referencia_marca = models.CharField(
        max_length=150,
        blank=True,
        null=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["lote", "is_ingresado"]),
            models.Index(fields=["lote", "is_resultado_ingresado"]),
            models.Index(fields=["lote", "is_revisado"]),
            models.Index(fields=["referencia_equipo", "fecha_toma"]),
            models.Index(fields=["fecha_registro"]),
        ]

    @classmethod
    def _next_identifier(cls):
        """Return the next yearly sample identifier while ignoring legacy malformed IDs."""
        prefix = f"M{timezone.now().year}"
        highest = 0
        for identifier in cls.objects.filter(id__startswith=prefix).values_list("id", flat=True):
            suffix = identifier[len(prefix):]
            if suffix.isdigit():
                highest = max(highest, int(suffix))
        return f"{prefix}{highest + 1:04d}"

    def save(self, *args, **kwargs):
        # Equipo y punto de medida no identifican una muestra: se pueden tomar
        # muchas muestras del mismo punto para construir su histórico.  El ID es
        # global y se genera de manera serializada para que dos ingresos rápidos
        # (o dos peticiones simultáneas) nunca reutilicen el mismo consecutivo.
        if self._state.adding and not self.id:
            with transaction.atomic():
                if connection.vendor == "postgresql":
                    # Advisory lock shared by every worker, released al cerrar la
                    # transacción. No depende de que ya exista una fila que bloquear.
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [81423019])
                self.id = self._next_identifier()
                return super().save(*args, **kwargs)

        return super().save(*args, **kwargs)


class HistorialMuestra(models.Model):
    muestra = models.ForeignKey(
        Muestra,
        on_delete=models.CASCADE,
        related_name="historial",
    )
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="cambios_muestras",
    )
    accion = models.CharField(max_length=30, default="actualizacion")
    cambios = models.JSONField(default=dict)
    estado_anterior = models.JSONField(default=dict)
    estado_nuevo = models.JSONField(default=dict)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-creado_en", "-id"]
        indexes = [
            models.Index(fields=["muestra", "creado_en"]),
        ]

    def __str__(self):
        return f"{self.muestra_id} - {self.accion} - {self.creado_en:%Y-%m-%d %H:%M}"

from django.db import models
from apps.users.api.models.index import User
from django.core.validators import MinValueValidator
import uuid
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra


class Resultado(models.Model):
    ESTATUS_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('preliminar', 'Preliminar'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    ]
    
    prueba_muestra = models.ForeignKey(PruebaMuestra, on_delete=models.CASCADE, related_name='resultados')
   
    resultado = models.TextField()
    fecha_medicion = models.DateTimeField()
    usuario_medicion = models.ForeignKey(User, on_delete=models.PROTECT, related_name='resultados_medidos')
    estatus = models.CharField(max_length=20, choices=ESTATUS_CHOICES, default='pendiente')
    observaciones = models.TextField(blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['prueba_muestra', 'estatus']),
            models.Index(fields=['prueba_muestra', 'fecha_registro']),
            models.Index(fields=['fecha_medicion']),
            models.Index(fields=['fecha_registro']),
        ]
    
    def __str__(self):
        return f"Resultado {self.id} - {self.prueba_muestra.prueba.acronimo}"

class HistoricoResultado(models.Model):
    resultado = models.ForeignKey(Resultado, on_delete=models.CASCADE, related_name='historico')
    resultado_anterior = models.TextField()

    fecha_medicion_anterior = models.DateTimeField()
    usuario_medicion = models.ForeignKey(User, on_delete=models.PROTECT)
    observaciones_anterior = models.TextField(blank=True, null=True)
    usuario_modificacion = models.ForeignKey(User, on_delete=models.PROTECT, related_name='modificaciones_resultados')
    fecha_modificacion = models.DateTimeField(auto_now_add=True)
    motivo_cambio = models.TextField()

    class Meta:
        indexes = [
            models.Index(fields=['resultado', 'fecha_modificacion']),
        ]
    
    def __str__(self):
        return f"Histórico {self.id} - Resultado {self.resultado.id}"

class RevisionResultado(models.Model):
    resultado = models.ForeignKey(Resultado, on_delete=models.CASCADE, related_name='revisiones')
    usuario_revision = models.ForeignKey(User, on_delete=models.PROTECT)
    estatus_anterior = models.CharField(max_length=20, blank=True, null=True)
    estatus_nuevo = models.CharField(max_length=20)
    observaciones = models.TextField(blank=True, null=True)
    fecha_revision = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['resultado', 'fecha_revision']),
            models.Index(fields=['estatus_nuevo']),
        ]
    
    def __str__(self):
        return f"Revisión {self.id} - Resultado {self.resultado.id}"


class VersionInterpretacion(models.Model):
    """Instantánea inmutable de una interpretación guardada por muestra."""

    ORIGEN_CHOICES = [
        ("manual", "Manual"),
        ("importacion", "Importación"),
        ("ia", "Asistente IA"),
        ("legado", "Histórico previo"),
    ]

    muestra = models.ForeignKey(
        "muestras.Muestra",
        on_delete=models.CASCADE,
        related_name="versiones_interpretacion",
    )
    version = models.PositiveIntegerField()
    contenido = models.JSONField(default=dict)
    motivo = models.TextField(blank=True, default="")
    origen = models.CharField(max_length=20, choices=ORIGEN_CHOICES, default="manual")
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interpretaciones_versionadas",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["muestra", "version"], name="resultado_version_interpretacion_unica"),
        ]
        indexes = [
            models.Index(fields=["muestra", "creado_en"], name="resultado_v_muestra_48ce8d_idx"),
            models.Index(fields=["origen", "creado_en"], name="resultado_v_origen_b3ef20_idx"),
        ]

    def __str__(self):
        return f"Interpretación {self.muestra_id} v{self.version}"

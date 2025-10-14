from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.users.api.models.index import User
from apps.muestras.api.models.muestras.index import Muestra
from apps.misc.api.models.pruebas.index import Prueba


class PruebaMuestra(models.Model):
    # Relación base
    muestra = models.ForeignKey(Muestra, on_delete=models.CASCADE, related_name='resultados')
    prueba = models.ForeignKey(Prueba, on_delete=models.PROTECT)

    # Control de flujo
    usuario_solicitud = models.ForeignKey(User, on_delete=models.PROTECT, related_name="pruebas_solicitadas")
    usuario_medicion = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="pruebas_medidas")
    usuario_revision = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="pruebas_revisadas")

    # Fechas de proceso
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    fecha_medicion = models.DateTimeField(null=True, blank=True)
    fecha_revision = models.DateTimeField(null=True, blank=True)

    # Datos de resultado (ya dentro del modelo)
    valor = models.CharField(max_length=255, null=True, blank=True)
    unidad = models.CharField(max_length=20, null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)

    # Estado general
    estatus = models.CharField(
        max_length=20,
        default='pendiente',
        choices=[
            ('pendiente', 'Pendiente'),
            ('en_proceso', 'En Proceso'),
            ('completado', 'Completado'),
            ('rechazado', 'Rechazado'),
            ('aprobado', 'Aprobado'),
        ]
    )

    completada = models.BooleanField(default=False)
    is_revisada = models.BooleanField(default=False)

    class Meta:
        unique_together = ('muestra', 'prueba')
        verbose_name = "Prueba aplicada a muestra"
        verbose_name_plural = "Pruebas aplicadas a muestras"

    def __str__(self):
        return f"{self.muestra.codigo if hasattr(self.muestra, 'codigo') else self.muestra.id} - {self.prueba.nombre}"

    # ✅ Métodos de utilidad para flujo
    def registrar_resultado(self, valor, usuario, observaciones=None):
        """Registra un resultado y actualiza el estado"""
        self.valor = valor
        self.usuario_medicion = usuario
        self.fecha_medicion = timezone.now()
        self.observaciones = observaciones or ''
        self.estatus = 'completado'
        self.completada = True
        self.save()

    def revisar_resultado(self, usuario, estatus_nuevo='aprobado', observaciones=None):
        """Revisión del resultado"""
        self.usuario_revision = usuario
        self.fecha_revision = timezone.now()
        self.estatus = estatus_nuevo
        if observaciones:
            self.observaciones = (self.observaciones or '') + f"\n[Revisión] {observaciones}"
        self.save()

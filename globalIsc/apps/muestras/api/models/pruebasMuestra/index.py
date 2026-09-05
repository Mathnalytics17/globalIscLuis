from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from apps.users.api.models.index import User
from apps.muestras.api.models.muestras.index import Muestra
from apps.misc.api.models.pruebas.index import Prueba
from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CatalogoTecnico,
    CatalogoTecnicoItem,
    EscalaComparacion,
    EscalaComparacionItem,
    CriterioEvaluacionLimite,
)
from apps.misc.api.models.technicalCatalogs.index import Condicion, EquipoPrueba, MetodoEquipo
from apps.misc.api.models.lotesPruebasPredefinidos.index import LotePruebasPredefinido


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

    # Configuración de la asignación
    equipo_configurado = models.ForeignKey(
        EquipoPrueba,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='pruebas_muestra_configuradas',
    )
    metodo_configurado = models.ForeignKey(
        MetodoEquipo,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='pruebas_muestra_configuradas',
    )
    condicion_catalogo = models.ForeignKey(
        Condicion,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="pruebas_muestra",
    )
    condicion_configurada = models.CharField(max_length=120, null=True, blank=True)
    unidad_configurada = models.CharField(max_length=40, null=True, blank=True)
    configuracion_resultados = models.JSONField(
        default=dict,
        blank=True,
        help_text="Unidad y condicion aplicadas por cada resultado de la prueba.",
    )
    lote_predefinido = models.ForeignKey(
        LotePruebasPredefinido,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='pruebas_asignadas',
    )
    criterio_evaluacion = models.ForeignKey(
        CriterioEvaluacionLimite,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='pruebas_muestra',
    )
    criterio_limite_catalogo = models.ForeignKey(
        CatalogoTecnico,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='pruebas_muestra_criterio',
    )
    criterio_limite_item = models.ForeignKey(
        CatalogoTecnicoItem,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='pruebas_muestra_criterio',
    )
    criterio_limite_escala = models.ForeignKey(
        EscalaComparacion,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='pruebas_muestra_criterio',
    )
    criterio_limite_escala_item = models.ForeignKey(
        EscalaComparacionItem,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='pruebas_muestra_criterio',
    )
    criterio_limite_valor = models.TextField(
        blank=True,
        null=True,
        help_text="Criterio elegido al asignar la prueba. Acepta valor simple o JSON con valores por campo de limite.",
    )
    estado_asignacion = models.CharField(
        max_length=20,
        default='confirmada',
        choices=[
            ('borrador', 'Borrador'),
            ('confirmada', 'Confirmada'),
        ]
    )
    fecha_confirmacion = models.DateTimeField(null=True, blank=True)

    # Datos de resultado (ya dentro del modelo)
    valor = models.CharField(max_length=255, null=True, blank=True)
    unidad = models.CharField(max_length=20, null=True, blank=True)
    observaciones = models.TextField(blank=True, null=True)
    evaluacion_limite = models.JSONField(blank=True, null=True)
    estado_limite = models.CharField(max_length=40, blank=True, null=True)

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
        indexes = [
            models.Index(fields=['muestra', 'estatus']),
            models.Index(fields=['muestra', 'estado_asignacion']),
            models.Index(fields=['muestra', 'completada']),
            models.Index(fields=['muestra', 'is_revisada']),
            models.Index(fields=['prueba', 'estatus']),
            models.Index(fields=['fecha_solicitud']),
            models.Index(fields=['fecha_medicion']),
            models.Index(fields=['fecha_revision']),
        ]
        verbose_name = "Prueba aplicada a muestra"
        verbose_name_plural = "Pruebas aplicadas a muestras"

    def __str__(self):
        return f"{self.muestra.id} - {self.prueba.acronimo}"

    # ✅ Métodos de utilidad para flujo
    def registrar_resultado(self, valor, usuario, observaciones=None):
        """Registra un resultado y actualiza el estado"""
        valor = "" if valor is None else str(valor)
        self.valor = valor[:255]
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

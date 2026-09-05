from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.activesTree.api.models.machines.index import Maquina
from apps.misc.api.models.companies.index import Empresa
from apps.muestras.api.models.muestras.index import Muestra


class Carpeta(models.Model):
    is_pt_medida = models.BooleanField(default=False)
    id_parent_node = models.CharField(max_length=255, default='-1')
    nombre = models.CharField(max_length=255)
    compania = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name='carpetas')
    typeFolder = models.CharField(max_length=255)
    isMachine = models.BooleanField(default=False)
    machine = models.ForeignKey(
        Maquina,
        on_delete=models.CASCADE,
        related_name='maquina_folder',
        null=True,
        blank=True,
    )
    muestra = models.ForeignKey(
        Muestra,
        on_delete=models.CASCADE,
        related_name='muestra_folder',
        null=True,
        blank=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=['compania', 'typeFolder']),
            models.Index(fields=['id_parent_node']),
            models.Index(fields=['machine']),
            models.Index(fields=['muestra']),
        ]

    def __str__(self):
        return f'{self.nombre} ({self.compania.nombre})'


class PuntoMuestreo(models.Model):
    """Nodo terminal administrado desde el arbol, siempre hijo de una maquina."""

    maquina = models.ForeignKey(
        Maquina,
        on_delete=models.PROTECT,
        related_name='puntos_muestreo',
    )
    nombre = models.CharField(max_length=150)
    codigo = models.CharField(max_length=80, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True, db_index=True)
    creado_por = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='puntos_muestreo_creados',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['maquina', 'nombre'],
                condition=Q(activo=True),
                name='unique_active_sampling_point_name_per_machine',
            ),
        ]
        indexes = [models.Index(fields=['maquina', 'activo'])]

    @property
    def compania_id(self):
        return self.maquina.empresa_id

    def __str__(self):
        return f'{self.maquina.nombre} / {self.nombre}'


class AsignacionPuntoMuestreo(models.Model):
    """Historial auditable de la clasificacion posterior de una muestra."""

    ORIGEN_CHOICES = [('manual', 'Manual'), ('lote', 'Lote')]

    muestra = models.ForeignKey(
        Muestra,
        on_delete=models.CASCADE,
        related_name='asignaciones_punto_muestreo',
    )
    punto_muestreo = models.ForeignKey(
        PuntoMuestreo,
        on_delete=models.PROTECT,
        related_name='asignaciones',
    )
    origen = models.CharField(max_length=20, choices=ORIGEN_CHOICES, default='manual')
    activa = models.BooleanField(default=True, db_index=True)
    asignado_por = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='asignaciones_punto_muestreo_realizadas',
    )
    asignado_en = models.DateTimeField(auto_now_add=True)
    finalizado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ['-asignado_en', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['muestra'],
                condition=Q(activa=True),
                name='one_active_sampling_point_per_sample',
            ),
        ]
        indexes = [
            models.Index(fields=['punto_muestreo', 'activa']),
            models.Index(fields=['muestra', 'activa']),
        ]

    def close(self):
        self.activa = False
        self.finalizado_en = timezone.now()
        self.save(update_fields=['activa', 'finalizado_en'])

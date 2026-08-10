from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.misc.api.models.pruebas.index import Prueba
from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CatalogoTecnico,
    CatalogoTecnicoItem,
    EscalaComparacion,
    EscalaComparacionItem,
)
from apps.misc.api.models.technicalCatalogs.index import Condicion, EquipoPrueba, MetodoEquipo
from apps.misc.api.models.tipoGestionMuestra.index import TipoGestionMuestra


class LotePruebasPredefinido(models.Model):
    TIPO_LOTE_CHOICES = [
        ("gestion", "Por gestión"),
        ("personalizado", "Personalizado"),
    ]

    nombre = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, null=True)
    tipo_lote = models.CharField(max_length=20, choices=TIPO_LOTE_CHOICES, default="personalizado")
    tipo_gestion = models.ForeignKey(
        TipoGestionMuestra,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="lotes_pruebas_predefinidos",
    )
    es_default = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre", "id"]
        indexes = [
            models.Index(fields=["tipo_lote"]),
            models.Index(fields=["tipo_gestion"]),
            models.Index(fields=["activo"]),
        ]

    def __str__(self):
        return self.nombre

    def clean(self):
        if self.tipo_lote == "gestion" and not self.tipo_gestion_id:
            raise ValidationError({"tipo_gestion": "Debe seleccionar un tipo de gestión para este lote."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def soft_delete(self):
        self.activo = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["activo", "deleted_at", "updated_at"])


class LotePruebasPredefinidoDetalle(models.Model):
    lote = models.ForeignKey(
        LotePruebasPredefinido,
        on_delete=models.CASCADE,
        related_name="detalles",
    )
    prueba = models.ForeignKey(
        Prueba,
        on_delete=models.PROTECT,
        related_name="lotes_predefinidos_detalle",
    )
    equipo_prueba = models.ForeignKey(
        EquipoPrueba,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="lotes_predefinidos_detalle",
    )
    metodo_equipo = models.ForeignKey(
        MetodoEquipo,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="lotes_predefinidos_detalle",
    )
    condicion = models.ForeignKey(
        Condicion,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="lotes_predefinidos_detalle",
    )
    condicion_texto = models.CharField(max_length=120, blank=True, null=True)
    unidad = models.CharField(max_length=40, blank=True, null=True)
    configuracion_resultados = models.JSONField(
        default=dict,
        blank=True,
        help_text="Unidad y condicion predefinidas por resultado de la prueba.",
    )
    criterio_limite_catalogo = models.ForeignKey(
        CatalogoTecnico,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="lotes_predefinidos_detalle_criterio",
    )
    criterio_limite_item = models.ForeignKey(
        CatalogoTecnicoItem,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="lotes_predefinidos_detalle_criterio",
    )
    criterio_limite_escala = models.ForeignKey(
        EscalaComparacion,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="lotes_predefinidos_detalle_criterio",
    )
    criterio_limite_escala_item = models.ForeignKey(
        EscalaComparacionItem,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="lotes_predefinidos_detalle_criterio",
    )
    criterio_limite_valor = models.TextField(
        blank=True,
        null=True,
        help_text="Criterio preseleccionado. Acepta valor simple o JSON con valores por campo de limite.",
    )
    orden = models.PositiveIntegerField(default=1)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["orden", "id"]
        unique_together = [("lote", "prueba", "orden")]

    def __str__(self):
        return f"{self.lote.nombre} - {self.prueba.acronimo}"

    def clean(self):
        if self.metodo_equipo_id and self.equipo_prueba_id and self.metodo_equipo.equipo_prueba_id != self.equipo_prueba_id:
            raise ValidationError({"metodo_equipo": "El método seleccionado no pertenece al equipo indicado."})

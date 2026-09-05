from django.core.exceptions import ValidationError
from django.db import models

from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CatalogoTecnico,
    CatalogoTecnicoItem,
    CampoTecnicoMuestra,
)
from apps.muestras.api.models.muestras.index import Muestra


class MuestraAtributoTecnico(models.Model):
    muestra = models.ForeignKey(
        Muestra,
        on_delete=models.CASCADE,
        related_name="atributos_tecnicos",
    )
    catalogo = models.ForeignKey(
        CatalogoTecnico,
        on_delete=models.PROTECT,
        related_name="atributos_muestra",
    )
    campo_tecnico = models.ForeignKey(
        CampoTecnicoMuestra,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="atributos_muestra",
    )
    item = models.ForeignKey(
        CatalogoTecnicoItem,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="atributos_muestra",
    )
    desconocido = models.BooleanField(default=False)
    observacion = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["muestra", "campo_tecnico"],
                name="unique_sample_dynamic_field_attribute",
            )
        ]
        indexes = [
            models.Index(fields=["muestra", "catalogo"]),
            models.Index(fields=["muestra", "campo_tecnico"]),
            models.Index(fields=["catalogo", "item"]),
            models.Index(fields=["desconocido"]),
        ]

    def clean(self):
        errors = {}
        if self.desconocido and self.item_id:
            errors["item"] = "No debe seleccionar item si el atributo es desconocido."
        if not self.desconocido and not self.item_id:
            errors["item"] = "Debe seleccionar item o marcar el atributo como desconocido."
        if self.item_id and self.item.catalogo_id != self.catalogo_id:
            errors["item"] = "El item debe pertenecer al catalogo indicado."
        if self.campo_tecnico_id:
            if self.campo_tecnico.catalogo_id != self.catalogo_id:
                errors["campo_tecnico"] = "El campo tecnico debe apuntar al mismo catalogo."
            if self.muestra_id:
                applies = self.campo_tecnico.tipo_muestra in ["ambos", self.muestra.tipo_muestra]
                if not applies:
                    errors["campo_tecnico"] = "El campo tecnico no aplica al tipo de muestra."
        if self.muestra_id and self.catalogo_id:
            applies = self.catalogo.tipo_muestra in ["ambos", self.muestra.tipo_muestra]
            if not applies:
                errors["catalogo"] = "El catalogo no aplica al tipo de muestra."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        value = "Desconocido" if self.desconocido else str(self.item)
        return f"{self.muestra_id} - {self.catalogo.nombre}: {value}"

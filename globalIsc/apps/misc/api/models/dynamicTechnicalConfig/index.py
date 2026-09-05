import re

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from apps.misc.api.models.pruebas.index import (
    Prueba,
    PruebaResultado,
    PruebaResultadoDivision,
    PruebaResultadoComponente,
)


def normalize_scale_token(value):
    text = str(value or "").strip().lower()
    text = re.sub(r"(?<=\d)[,.](?=\d)", "_", text)
    return slugify(text).replace("-", "_")


class SoftDeleteModel(models.Model):
    activo = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def soft_delete(self):
        self.activo = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["activo", "deleted_at", "updated_at"])

    def restore(self):
        self.activo = True
        self.deleted_at = None
        self.save(update_fields=["activo", "deleted_at", "updated_at"])


class CatalogoTecnico(SoftDeleteModel):
    TIPO_MUESTRA_CHOICES = [
        ("aceite", "Aceite"),
        ("grasa", "Grasa"),
        ("ambos", "Ambos"),
    ]

    nombre = models.CharField(max_length=120)
    codigo = models.SlugField(max_length=80, unique=True)
    tipo_muestra = models.CharField(max_length=20, choices=TIPO_MUESTRA_CHOICES, default="ambos")
    descripcion = models.TextField(blank=True, null=True)
    es_requerido_en_muestra = models.BooleanField(default=False)
    permite_desconocido = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["orden", "nombre"]

    def save(self, *args, **kwargs):
        if not self.codigo and self.nombre:
            self.codigo = slugify(self.nombre).replace("-", "_")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class CampoTecnicoMuestra(SoftDeleteModel):
    TIPO_MUESTRA_CHOICES = CatalogoTecnico.TIPO_MUESTRA_CHOICES

    nombre_visible = models.CharField(max_length=140)
    codigo = models.SlugField(max_length=100)
    tipo_muestra = models.CharField(max_length=20, choices=TIPO_MUESTRA_CHOICES, default="ambos")
    catalogo = models.ForeignKey(CatalogoTecnico, on_delete=models.PROTECT, related_name="campos_muestra")
    obligatorio = models.BooleanField(default=False)
    permite_desconocido = models.BooleanField(default=True)
    visible_en_ingreso = models.BooleanField(default=True)
    visible_en_asignacion = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=1)
    ayuda = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ["tipo_muestra", "orden", "nombre_visible"]
        unique_together = ("tipo_muestra", "codigo")

    def save(self, *args, **kwargs):
        if not self.codigo and self.nombre_visible:
            self.codigo = slugify(self.nombre_visible).replace("-", "_")
        super().save(*args, **kwargs)

    def clean(self):
        if not self.catalogo_id:
            return
        catalog_type = self.catalogo.tipo_muestra
        incompatible = (
            (self.tipo_muestra == "ambos" and catalog_type != "ambos")
            or (
                self.tipo_muestra != "ambos"
                and catalog_type not in ["ambos", self.tipo_muestra]
            )
        )
        if incompatible:
            raise ValidationError({
                "catalogo": "El catalogo asociado no aplica a todos los tipos de muestra del campo."
            })

    def __str__(self):
        return f"{self.nombre_visible} ({self.tipo_muestra})"


class CatalogoTecnicoCampo(SoftDeleteModel):
    catalogo = models.ForeignKey(CatalogoTecnico, on_delete=models.CASCADE, related_name="campos")
    nombre = models.CharField(max_length=120)
    codigo = models.SlugField(max_length=80)
    tipo_dato = models.CharField(
        max_length=20,
        choices=[("texto", "Texto"), ("numero", "Número"), ("decimal", "Decimal"), ("booleano", "Booleano")],
        default="texto",
    )
    unidad = models.CharField(max_length=30, blank=True, null=True)
    orden = models.PositiveIntegerField(default=1)
    es_visible_en_muestra = models.BooleanField(default=False)
    es_campo_limite = models.BooleanField(default=False)

    class Meta:
        ordering = ["catalogo__orden", "orden", "nombre"]
        unique_together = ("catalogo", "codigo")

    def save(self, *args, **kwargs):
        if not self.codigo and self.nombre:
            self.codigo = slugify(self.nombre).replace("-", "_")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.catalogo.nombre} · {self.nombre}"


class CatalogoTecnicoItem(SoftDeleteModel):
    catalogo = models.ForeignKey(CatalogoTecnico, on_delete=models.CASCADE, related_name="items")
    nombre = models.CharField(max_length=160)
    codigo = models.SlugField(max_length=120)
    descripcion = models.TextField(blank=True, null=True)
    metadata = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ["catalogo__orden", "nombre"]
        unique_together = ("catalogo", "codigo")

    def save(self, *args, **kwargs):
        if not self.codigo and self.nombre:
            self.codigo = slugify(self.nombre).replace("-", "_")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.catalogo.nombre} · {self.nombre}"


class CatalogoTecnicoItemValor(models.Model):
    item = models.ForeignKey(CatalogoTecnicoItem, on_delete=models.CASCADE, related_name="valores")
    campo = models.ForeignKey(CatalogoTecnicoCampo, on_delete=models.CASCADE, related_name="valores")
    valor = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("item", "campo")
        ordering = ["item__nombre", "campo__orden"]

    def __str__(self):
        return f"{self.item} · {self.campo.codigo}: {self.valor}"

    def clean(self):
        if self.item_id and self.campo_id and self.item.catalogo_id != self.campo.catalogo_id:
            raise ValidationError({"campo": "El campo debe pertenecer al catálogo del ítem."})


class EscalaComparacion(SoftDeleteModel):
    nombre = models.CharField(max_length=140)
    codigo = models.SlugField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["nombre"]

    def save(self, *args, **kwargs):
        if not self.codigo and self.nombre:
            self.codigo = slugify(self.nombre).replace("-", "_")
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class EscalaComparacionItem(SoftDeleteModel):
    escala = models.ForeignKey(EscalaComparacion, on_delete=models.CASCADE, related_name="items")
    etiqueta = models.CharField(max_length=80)
    valor_normalizado = models.SlugField(max_length=100)
    orden = models.PositiveIntegerField(default=1)
    numero_base = models.DecimalField(max_digits=12, decimal_places=4, blank=True, null=True)
    modificador = models.CharField(max_length=20, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["escala__nombre", "orden", "id"]
        unique_together = ("escala", "valor_normalizado")

    def save(self, *args, **kwargs):
        if not self.valor_normalizado and self.etiqueta:
            self.valor_normalizado = normalize_scale_token(self.etiqueta)
        elif self.valor_normalizado:
            self.valor_normalizado = normalize_scale_token(self.valor_normalizado)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.escala.nombre} ? {self.etiqueta}"


class PruebaFuenteLimite(SoftDeleteModel):
    TIPO_LIMITE_CHOICES = [
        ("catalogo", "Catalogo tecnico"),
        ("campo_muestra", "Campo tecnico de muestra"),
        ("seleccion_asignacion", "Seleccion al asignar"),
        ("global", "Global"),
        ("sin_limite", "Sin limite"),
    ]
    POLITICA_EVALUACION_CHOICES = [
        ("todas_deben_cumplir", "Todas deben cumplir"),
        ("solo_informativo", "Solo informativo"),
    ]
    MODO_SELECCION_CHOICES = [
        ("desde_muestra_editable", "Tomar de la muestra y permitir reemplazo"),
        ("seleccionar_asignacion", "Seleccionar al asignar la prueba"),
        ("fijo", "Usar configuración fija"),
    ]

    prueba = models.ForeignKey(Prueba, on_delete=models.CASCADE, related_name="fuentes_limite")
    tipo_limite = models.CharField(max_length=30, choices=TIPO_LIMITE_CHOICES, default="catalogo")
    catalogo_fuente = models.ForeignKey(
        CatalogoTecnico,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="fuentes_limite",
    )
    campo_tecnico_muestra = models.ForeignKey(
        CampoTecnicoMuestra,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="fuentes_limite",
    )
    prioridad = models.PositiveIntegerField(default=100)
    politica_evaluacion = models.CharField(
        max_length=30,
        choices=POLITICA_EVALUACION_CHOICES,
        default="todas_deben_cumplir",
    )
    minimo_campos_cumplidos = models.PositiveIntegerField(blank=True, null=True)
    configuracion_regla = models.JSONField(default=dict, blank=True)
    reglas_resultados = models.JSONField(default=dict, blank=True)
    modo_seleccion = models.CharField(
        max_length=30,
        choices=MODO_SELECCION_CHOICES,
        default="seleccionar_asignacion",
    )
    version = models.PositiveIntegerField(default=1)
    publicada = models.BooleanField(default=False)
    notas = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["prioridad", "prueba__nombre_variable"]

    def __str__(self):
        return f"{self.prueba} · {self.catalogo_fuente}"

    def clean(self):
        if self.tipo_limite == "catalogo" and not self.catalogo_fuente_id:
            raise ValidationError({"catalogo_fuente": "Seleccione un catalogo para limites por catalogo."})
        if self.tipo_limite == "campo_muestra" and not self.campo_tecnico_muestra_id:
            raise ValidationError({"campo_tecnico_muestra": "Seleccione el campo tecnico de muestra."})
        if self.tipo_limite == "campo_muestra" and self.campo_tecnico_muestra_id:
            self.catalogo_fuente = self.campo_tecnico_muestra.catalogo
        if self.tipo_limite == "seleccion_asignacion" and not self.catalogo_fuente_id:
            raise ValidationError({"catalogo_fuente": "Seleccione el catalogo o criterio disponible al asignar."})
        if self.tipo_limite in ["global", "sin_limite"]:
            self.catalogo_fuente = None
            self.campo_tecnico_muestra = None
        if self.politica_evaluacion not in dict(self.POLITICA_EVALUACION_CHOICES):
            raise ValidationError({"politica_evaluacion": "Politica de evaluacion obsoleta."})


class CriterioEvaluacionLimite(SoftDeleteModel):
    TIPO_CRITERIO_CHOICES = [
        ("catalogo_item", "Item de catalogo"),
        ("escala_item", "Item de escala"),
        ("valor_fijo", "Valor fijo"),
        ("booleano", "Booleano"),
        ("opcion", "Opcion"),
    ]

    fuente_limite = models.ForeignKey(PruebaFuenteLimite, on_delete=models.CASCADE, related_name="criterios")
    nombre = models.CharField(max_length=160)
    codigo = models.SlugField(max_length=140)
    tipo_criterio = models.CharField(max_length=30, choices=TIPO_CRITERIO_CHOICES, default="catalogo_item")
    catalogo_item = models.ForeignKey(
        CatalogoTecnicoItem,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="criterios_limite",
    )
    escala_item = models.ForeignKey(
        EscalaComparacionItem,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="criterios_limite",
    )
    valor = models.CharField(max_length=120, blank=True, null=True)
    valores_limite = models.JSONField(default=dict, blank=True)
    descripcion = models.TextField(blank=True, null=True)
    orden = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["fuente_limite", "orden", "nombre"]
        unique_together = ("fuente_limite", "codigo")

    def save(self, *args, **kwargs):
        if not self.codigo and self.nombre:
            self.codigo = slugify(self.nombre).replace("-", "_")
        super().save(*args, **kwargs)

    def clean(self):
        errors = {}
        if self.tipo_criterio == "catalogo_item":
            if not self.catalogo_item_id:
                errors["catalogo_item"] = "Seleccione un item de catalogo."
            elif (
                self.fuente_limite_id
                and self.fuente_limite.catalogo_fuente_id
                and self.catalogo_item.catalogo_id != self.fuente_limite.catalogo_fuente_id
            ):
                errors["catalogo_item"] = "El item no pertenece al catalogo de la fuente."
        if self.tipo_criterio == "escala_item" and not self.escala_item_id:
            errors["escala_item"] = "Seleccione un item de escala."
        if self.tipo_criterio in ["valor_fijo", "booleano", "opcion"] and self.valor in [None, ""]:
            errors["valor"] = "Ingrese el valor del criterio."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.fuente_limite} - {self.nombre}"


class PruebaFuenteCatalogo(models.Model):
    fuente_limite = models.ForeignKey(
        PruebaFuenteLimite,
        on_delete=models.CASCADE,
        related_name="catalogos_configurados",
    )
    catalogo = models.ForeignKey(
        CatalogoTecnico,
        on_delete=models.PROTECT,
        related_name="fuentes_limite_configuradas",
    )
    campo_tecnico_muestra = models.ForeignKey(
        CampoTecnicoMuestra,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="fuentes_limite_configuradas",
    )
    orden = models.PositiveIntegerField(default=1)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["orden", "id"]
        unique_together = ("fuente_limite", "catalogo")

    def clean(self):
        if (
            self.campo_tecnico_muestra_id
            and self.campo_tecnico_muestra.catalogo_id != self.catalogo_id
        ):
            raise ValidationError({
                "campo_tecnico_muestra": "El campo técnico debe usar el catálogo seleccionado."
            })


class CriterioCatalogoSeleccion(models.Model):
    criterio = models.ForeignKey(
        CriterioEvaluacionLimite,
        on_delete=models.CASCADE,
        related_name="selecciones_catalogo",
    )
    catalogo = models.ForeignKey(CatalogoTecnico, on_delete=models.PROTECT)
    item = models.ForeignKey(CatalogoTecnicoItem, on_delete=models.PROTECT)

    class Meta:
        ordering = ["catalogo__orden", "catalogo__nombre"]
        unique_together = ("criterio", "catalogo")

    def clean(self):
        if self.item_id and self.catalogo_id and self.item.catalogo_id != self.catalogo_id:
            raise ValidationError({"item": "El item no pertenece al catálogo seleccionado."})


class PruebaLimiteCampo(SoftDeleteModel):
    OPERADOR_CHOICES = [
        ("max", "<= máximo"),
        ("min", ">= mínimo"),
        ("eq", "= exacto"),
        ("warn_max", "Alerta si supera"),
        ("warn_min", "Alerta si baja"),
        ("neq", "Diferente"),
        ("in", "En lista"),
        ("not_in", "No en lista"),
        ("scale_max", "Escala <= valor"),
        ("scale_min", "Escala >= valor"),
        ("informativo", "Informativo"),
    ]
    TIPO_COMPARACION_CHOICES = [
        ("numerica", "Numerica"),
        ("booleano", "Booleano"),
        ("escala", "Escala"),
        ("informativo", "Informativo"),
    ]

    fuente_limite = models.ForeignKey(PruebaFuenteLimite, on_delete=models.CASCADE, related_name="campos_limite")
    nombre = models.CharField(max_length=160)
    codigo = models.SlugField(max_length=140)
    operador = models.CharField(max_length=20, choices=OPERADOR_CHOICES, default="max")
    tipo_comparacion = models.CharField(max_length=30, choices=TIPO_COMPARACION_CHOICES, default="numerica")
    escala_comparacion = models.ForeignKey(
        EscalaComparacion,
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="campos_limite",
    )
    modo_ordinal = models.CharField(
        max_length=20,
        choices=[("orden", "Orden"), ("numero_base", "Numero base")],
        default="orden",
    )
    opciones_permitidas = models.JSONField(blank=True, null=True)
    # Mapa opcional de evaluación por valor exacto/opción/booleano.
    # Ejemplo:
    # {
    #   "si": {"estado": "FUERA_DE_LIMITE", "label": "NO DESEADO"},
    #   "no": {"estado": "NORMAL"}
    # }
    evaluacion_opciones = models.JSONField(blank=True, null=True)
    valor_global = models.CharField(max_length=120, blank=True, null=True)
    comentario_normal = models.TextField(blank=True, null=True)
    comentario_fuera_limite = models.TextField(blank=True, null=True)
    comentario_no_evaluable = models.TextField(blank=True, null=True)
    unidad = models.CharField(max_length=30, blank=True, null=True)
    resultado = models.ForeignKey(PruebaResultado, on_delete=models.SET_NULL, blank=True, null=True, related_name="campos_limite")
    division = models.ForeignKey(PruebaResultadoDivision, on_delete=models.SET_NULL, blank=True, null=True, related_name="campos_limite")
    componente = models.ForeignKey(PruebaResultadoComponente, on_delete=models.SET_NULL, blank=True, null=True, related_name="campos_limite")
    orden = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["fuente_limite", "orden", "nombre"]
        unique_together = ("fuente_limite", "codigo")

    def save(self, *args, **kwargs):
        if not self.codigo and self.nombre:
            self.codigo = slugify(self.nombre).replace("-", "_")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.fuente_limite} · {self.nombre}"

    def clean(self):
        errors = {}
        prueba_id = self.fuente_limite.prueba_id if self.fuente_limite_id else None
        if self.resultado_id and self.resultado.prueba_id != prueba_id:
            errors["resultado"] = "El resultado debe pertenecer a la prueba asociada."
        if self.division_id and (
            not self.resultado_id or self.division.resultado_id != self.resultado_id
        ):
            errors["division"] = "La división debe pertenecer al resultado seleccionado."
        if self.componente_id and (
            not self.division_id or self.componente.division_id != self.division_id
        ):
            errors["componente"] = "El componente debe pertenecer a la división seleccionada."
        if self.tipo_comparacion in ["escala", "escala_ordinal"] and not self.escala_comparacion_id:
            errors["escala_comparacion"] = "Seleccione una escala para comparaciones ordinales."
        if self.tipo_comparacion == "opcion" and self.opciones_permitidas not in [None, ""] and not isinstance(self.opciones_permitidas, list):
            errors["opciones_permitidas"] = "Las opciones permitidas deben ser una lista."
        if errors:
            raise ValidationError(errors)

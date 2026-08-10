from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.misc.api.models.technicalCatalogs.index import Condicion, MetodoEquipo, Unidad


class Prueba(models.Model):
    """
    CatÃ¡logo de pruebas/variables del laboratorio.

    SeparaciÃ³n conceptual:
    - metodo: mÃ©todo tÃ©cnico predefinido.
    - submetodos_tecnicos: submÃ©todos tÃ©cnicos del mÃ©todo seleccionado.
    - resultados: estructura propia de la prueba.

    Ejemplos de estructura de resultado:
    - Espuma -> divisiones Seq I, Seq II, Seq III -> componentes FI/EI, FII/EII, FIII/EIII.
    - Densidad -> divisiones 15Â°C, 20Â°C, 30Â°C -> componentes D15, D20, D30.
    - Resultado simple -> una divisiÃ³n principal -> un componente -> disposiciÃ³n directa.
    """

    nombre_variable = models.CharField(max_length=150)
    condicion = models.CharField(max_length=150, blank=True, null=True)
    acronimo = models.CharField(max_length=30, unique=True)
    unidad_medida = models.CharField(max_length=40, blank=True, null=True)
    unidad_catalogo = models.ForeignKey(
        Unidad,
        on_delete=models.PROTECT,
        related_name="pruebas",
        blank=True,
        null=True,
    )
    condicion_catalogo = models.ForeignKey(
        Condicion,
        on_delete=models.PROTECT,
        related_name="pruebas",
        blank=True,
        null=True,
    )

    # IMPORTANTE:
    # Este campo apunta al catÃ¡logo tÃ©cnico real:
    # /api/technical-catalogs/equipment-methods/
    # Modelo: MetodoEquipo
    metodo = models.ForeignKey(
        MetodoEquipo,
        on_delete=models.PROTECT,
        related_name="pruebas",
        blank=True,
        null=True,
    )

    activo = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre_variable"]
        indexes = [
            models.Index(fields=["activo"]),
            models.Index(fields=["acronimo"]),
            models.Index(fields=["nombre_variable"]),
        ]

    def __str__(self):
        return f"{self.acronimo} - {self.nombre_variable}"

    @property
    def equipo(self):
        if not self.metodo_id or not self.metodo:
            return None
        equipo = getattr(self.metodo, "equipo_prueba", None)
        if not equipo:
            return None
        return {
            "id": equipo.id,
            "codigo": equipo.codigo,
            "nombre": equipo.nombre,
        }

    @property
    def tiene_submetodos_tecnicos(self):
        return False

    def soft_delete(self):
        self.activo = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["activo", "deleted_at", "updated_at"])


class PruebaResultado(models.Model):
    """
    Resultado conceptual de una prueba.

    Ejemplos:
    - Resultado: Espuma
    - Resultado: Densidad
    - Resultado: Viscosidad

    El resultado puede ser simple o dividido.
    """

    prueba = models.ForeignKey(
        Prueba,
        on_delete=models.CASCADE,
        related_name="resultados",
        blank=True,
        null=True,
    )
    nombre = models.CharField(max_length=150)
    acronimo = models.CharField(max_length=30, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    unidad_medida = models.CharField(max_length=40, blank=True, null=True)
    unidad_catalogo = models.ForeignKey(
        Unidad,
        on_delete=models.PROTECT,
        related_name="resultados_prueba",
        blank=True,
        null=True,
    )
    orden = models.PositiveIntegerField(default=1)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["orden", "id"]
        indexes = [models.Index(fields=["activo"]), models.Index(fields=["orden"])]

    def __str__(self):
        return f"{self.prueba.acronimo} - {self.acronimo or self.nombre}"

    def save(self, *args, **kwargs):
        if self.unidad_catalogo_id:
            self.unidad_medida = self.unidad_catalogo.simbolo
        super().save(*args, **kwargs)


class PruebaResultadoDivision(models.Model):
    """
    DivisiÃ³n interna del resultado.

    AquÃ­ viven cosas como:
    - Seq I, Seq II, Seq III
    - 15Â°C, 20Â°C, 30Â°C
    - Principal, cuando el resultado es simple
    """

    resultado = models.ForeignKey(
        PruebaResultado,
        on_delete=models.CASCADE,
        related_name="divisiones",
    )
    nombre = models.CharField(max_length=150, blank=True, null=True)
    es_principal = models.BooleanField(default=False)
    orden = models.PositiveIntegerField(default=1)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["orden", "id"]
        indexes = [models.Index(fields=["activo"]), models.Index(fields=["orden"])]

    def __str__(self):
        return f"{self.resultado} - {self.nombre or 'Principal'}"


class PruebaResultadoComponente(models.Model):
    """
    Componente medible o visible dentro de una divisiÃ³n.

    Ejemplos:
    - FI, EI
    - FII, EII
    - D15
    - Resultado simple
    """

    division = models.ForeignKey(
        PruebaResultadoDivision,
        on_delete=models.CASCADE,
        related_name="componentes",
    )
    nombre = models.CharField(max_length=150)
    acronimo = models.CharField(max_length=30, blank=True, null=True)
    tipo_dato = models.CharField(
        max_length=20,
        default="numerico",
        choices=[
            ("numerico", "Numérico"),
            ("booleano", "Booleano"),
            ("escala", "Escala"),
            ("comentario", "Comentario"),
        ],
    )
    escala_comparacion = models.ForeignKey(
        "misc.EscalaComparacion",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="componentes_resultado",
    )
    opciones_resultado = models.JSONField(blank=True, null=True)
    etiqueta_verdadero = models.CharField(max_length=80, default="Sí", blank=True)
    etiqueta_falso = models.CharField(max_length=80, default="No", blank=True)
    requiere_valor = models.BooleanField(default=True)
    permite_observacion = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=1)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["orden", "id"]

    def __str__(self):
        return f"{self.division} - {self.acronimo or self.nombre}"

    def clean(self):
        if self.tipo_dato == "escala" and not self.escala_comparacion_id:
            raise ValidationError({"escala_comparacion": "Seleccione la escala del campo."})
        if self.tipo_dato == "booleano" and (
            not str(self.etiqueta_verdadero or "").strip()
            or not str(self.etiqueta_falso or "").strip()
        ):
            raise ValidationError("Defina las etiquetas para verdadero y falso.")

    def save(self, *args, **kwargs):
        if self.tipo_dato != "escala":
            self.escala_comparacion = None
        if self.tipo_dato == "comentario":
            self.requiere_valor = False
        super().save(*args, **kwargs)


class PruebaResultadoSeparador(models.Model):
    division = models.ForeignKey(
        PruebaResultadoDivision,
        on_delete=models.CASCADE,
        related_name="separadores",
    )
    simbolo = models.CharField(max_length=10)
    orden = models.PositiveIntegerField(default=1)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["orden", "id"]

    def __str__(self):
        return f"{self.division} - {self.simbolo}"


class PruebaResultadoDisposicion(models.Model):
    division = models.ForeignKey(
        PruebaResultadoDivision,
        on_delete=models.CASCADE,
        related_name="disposiciones",
    )
    nombre = models.CharField(max_length=150, default="Disposición principal")
    orden = models.PositiveIntegerField(default=1)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["orden", "id"]

    def __str__(self):
        return f"{self.division} - {self.nombre}"


class PruebaResultadoDisposicionItem(models.Model):
    TIPO_ITEM_CHOICES = [
        ("componente", "Componente"),
        ("separador", "Separador"),
    ]

    disposicion = models.ForeignKey(
        PruebaResultadoDisposicion,
        on_delete=models.CASCADE,
        related_name="items",
    )
    tipo = models.CharField(max_length=20, choices=TIPO_ITEM_CHOICES)
    componente = models.ForeignKey(
        PruebaResultadoComponente,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="items_disposicion",
    )
    separador = models.ForeignKey(
        PruebaResultadoSeparador,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="items_disposicion",
    )
    orden = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["orden", "id"]

    def __str__(self):
        if self.tipo == "componente" and self.componente:
            return self.componente.acronimo or self.componente.nombre
        if self.tipo == "separador" and self.separador:
            return self.separador.simbolo
        return "-"


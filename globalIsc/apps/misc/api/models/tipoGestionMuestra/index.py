from django.db import models
from apps.misc.api.models.companies.index import Empresa


class TipoGestionMuestra(models.Model):
    nombre = models.CharField(max_length=120)
    dias_habiles = models.PositiveIntegerField(default=0)
    dias_calendario = models.PositiveIntegerField(default=0)

    # Si está activo, lo pueden usar todas las empresas
    aplica_a_todos = models.BooleanField(default=True)

    # Si aplica_a_todos=False, solo estas empresas podrán verlo
    empresas_permitidas = models.ManyToManyField(
        Empresa,
        blank=True,
        related_name="tipos_gestion_muestras"
    )
    pruebas_sugeridas = models.ManyToManyField(
        "misc.Prueba",
        blank=True,
        related_name="tipos_gestion_sugeridos",
    )

    activo = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tipo de gestión de muestra"
        verbose_name_plural = "Tipos de gestión de muestras"
        ordering = ["nombre"]
        indexes = [
            models.Index(fields=["activo"]),
            models.Index(fields=["aplica_a_todos"]),
        ]

    def __str__(self):
        return self.nombre

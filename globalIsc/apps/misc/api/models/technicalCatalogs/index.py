from django.db import models


class EquipoPrueba(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"


class Unidad(models.Model):
    nombre = models.CharField(max_length=100)
    simbolo = models.CharField(max_length=25, unique=True)
    magnitud = models.CharField(max_length=80, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["magnitud", "nombre"]

    def __str__(self):
        return self.simbolo


class MetodoEquipo(models.Model):
    equipo_prueba = models.ForeignKey(
        EquipoPrueba,
        on_delete=models.PROTECT,
        related_name="metodos",
    )
    codigo = models.CharField(max_length=50)
    nombre = models.CharField(max_length=120)
    norma_referencia = models.CharField(max_length=120, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["equipo_prueba__nombre", "nombre"]
        unique_together = ("equipo_prueba", "codigo")

    def __str__(self):
        return f"{self.equipo_prueba.codigo} - {self.codigo}"


class Condicion(models.Model):
    nombre = models.CharField(max_length=100)
    magnitud = models.CharField(max_length=80, default="temperatura")
    valor = models.DecimalField(max_digits=12, decimal_places=4)
    unidad = models.ForeignKey(
        Unidad,
        on_delete=models.PROTECT,
        related_name="condiciones",
    )
    descripcion = models.TextField(blank=True, null=True)
    activo = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["magnitud", "nombre", "valor"]
        unique_together = ("nombre", "magnitud", "valor", "unidad")

    def __str__(self):
        return f"{self.nombre}: {self.valor} {self.unidad.simbolo}"

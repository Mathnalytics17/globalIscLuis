from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
import uuid


class ElementoAnalisis(models.Model):
    simbolo = models.CharField(max_length=5, unique=True)
    nombre = models.CharField(max_length=50, unique=True)
    es_desgaste = models.BooleanField(default=False)
    es_contaminante = models.BooleanField(default=False)
    es_aditivo = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.simbolo} - {self.nombre}"

class CategoriaLimite(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.nombre

class LimiteElemento(models.Model):
    NIVELES = [
        ('verde', 'Verde - Normal'),
        ('amarillo', 'Amarillo - Precaución'),
        ('rojo', 'Rojo - Peligro'),
    ]
    
    elemento = models.ForeignKey(ElementoAnalisis, on_delete=models.CASCADE)
    categoria = models.ForeignKey(CategoriaLimite, on_delete=models.CASCADE)
    limite_verde = models.FloatField(blank=True, null=True)
    limite_amarillo = models.FloatField(blank=True, null=True)
    limite_rojo = models.FloatField(blank=True, null=True)
    
    class Meta:
        unique_together = ('elemento', 'categoria')
    
    def __str__(self):
        return f"Límites para {self.elemento.nombre} en {self.categoria.nombre}"

class ComentarioElemento(models.Model):
    elemento = models.ForeignKey(ElementoAnalisis, on_delete=models.CASCADE)
    categoria = models.ForeignKey(CategoriaLimite, on_delete=models.CASCADE)
    comentario_verde = models.TextField(blank=True, null=True)
    comentario_amarillo = models.TextField(blank=True, null=True)
    comentario_rojo = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = ('elemento', 'categoria')
    
    def __str__(self):
        return f"Comentarios para {self.elemento.nombre} en {self.categoria.nombre}"

class LimiteViscosidad(models.Model):
    tipo = models.CharField(max_length=10)  # SAE, ISO, ATF, 2T
    grado = models.CharField(max_length=20)
    vmin = models.FloatField(blank=True, null=True)
    vmax = models.FloatField(blank=True, null=True)
    iv1 = models.IntegerField(blank=True, null=True)
    iv2 = models.IntegerField(blank=True, null=True)
    
    class Meta:
        unique_together = ('tipo', 'grado')
    
    def __str__(self):
        return f"Límites viscosidad {self.tipo} {self.grado}"

class LimiteCalidad(models.Model):
    tipo = models.CharField(max_length=10)  # API, ISO-L-, JASO, etc.
    grado = models.CharField(max_length=20)
    espuma1 = models.CharField(max_length=20, blank=True, null=True)
    espuma2 = models.CharField(max_length=20, blank=True, null=True)
    espuma3 = models.CharField(max_length=20, blank=True, null=True)
    chispa = models.IntegerField(blank=True, null=True)
    
    class Meta:
        unique_together = ('tipo', 'grado')
    
    def __str__(self):
        return f"Límites calidad {self.tipo} {self.grado}"
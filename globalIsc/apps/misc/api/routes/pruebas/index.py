from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
import uuid





class Prueba(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    metodo_referencia = models.CharField(max_length=100, blank=True, null=True)
    unidad_medida = models.CharField(max_length=20, blank=True, null=True)
    equipo_requerido = models.CharField(max_length=100, blank=True, null=True)
    activo = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
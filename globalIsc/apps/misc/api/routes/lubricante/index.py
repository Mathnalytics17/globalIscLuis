from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
import uuid

class Lubricante(models.Model):
    referencia = models.CharField(max_length=50, unique=True)
    nombre_comercial = models.CharField(max_length=100, blank=True, null=True)
    grado_viscosidad = models.CharField(max_length=20, blank=True, null=True)
    nivel_desempeno = models.CharField(max_length=50, blank=True, null=True)
    fabricante = models.CharField(max_length=100, blank=True, null=True)
    
    def __str__(self):
        return self.referencia
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
import uuid


class TipoEquipo(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return self.nombre

class ReferenciaEquipo(models.Model):
    tipo = models.ForeignKey(TipoEquipo, on_delete=models.PROTECT)
    codigo = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = ('tipo', 'codigo')
    
    def __str__(self):
        return f"{self.tipo.nombre} - {self.codigo}"
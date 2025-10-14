from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
import uuid
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType





class Prueba(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True, null=True)
    metodo_referencia = models.CharField(max_length=100, blank=True, null=True)
    unidad_medida = models.CharField(max_length=20, blank=True, null=True)
    is_subPrueba=models.BooleanField(default=False)
    parent_node=models.IntegerField(default=-1)
        # Campos para categorizar la prueba
    categoria = models.CharField(max_length=20,default='viscosidad', choices=[
        ('viscosidad', 'Viscosidad'),
        ('calidad', 'Calidad'),
        ('elementos', 'Elementos'),
        ('otro', 'Otro')
    ])
    activo = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.codigo} - {self.nombre}"
    

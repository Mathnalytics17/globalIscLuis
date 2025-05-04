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
    
class RelacionPruebaLimite(models.Model):
    """Modelo intermedio con relación genérica"""
    prueba = models.ForeignKey(Prueba, on_delete=models.CASCADE)
    
    # Relación genérica
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    limite = GenericForeignKey('content_type', 'object_id')
    type_operation=models.CharField(max_length=200,default='equal',null=True)
    symbol_operation=models.CharField(max_length=200,default='equal',null=True)
    # Campos adicionales para la relación
    tipo_equipo = models.CharField(max_length=100)
    tipo_lubricante = models.CharField(max_length=100)
    severidad = models.CharField(max_length=20, choices=[
        ('critico', 'Crítico'),
        ('advertencia', 'Advertencia'),
        ('normal', 'Normal')
    ])
    
    class Meta:
        unique_together = ('prueba', 'content_type', 'object_id', 'tipo_equipo', 'tipo_lubricante')
    
    def __str__(self):
        return f"{self.prueba.codigo} - {self.limite}"
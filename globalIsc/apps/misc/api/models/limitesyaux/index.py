from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
import uuid
from apps.misc.api.models.pruebas.index import Prueba

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class LimiteGenericoPrueba(models.Model):
    OPERACIONES = [
        ('<', 'Menor que'),
        ('<=', 'Menor o igual'),
        ('=', 'Igual'),
        ('>=', 'Mayor o igual'),
        ('>', 'Mayor que'),
    ]
    nombre = models.CharField(max_length=255,null=True, blank=True)
    valor = models.FloatField(null=True, blank=True)
    symbol_operation = models.CharField(max_length=2, choices=OPERACIONES)
    type_operation = models.CharField(max_length=50, null=True, blank=True)

class ElementoAnalisis(models.Model):
    OPERACIONES = [
        ('<', 'Menor que'),
        ('<=', 'Menor o igual'),
        ('=', 'Igual'),
        ('>=', 'Mayor o igual'),
        ('>', 'Mayor que'),
    ]
    simbolo = models.CharField(max_length=5, unique=True)
    nombre = models.CharField(max_length=50, unique=True)
    valor = models.FloatField(null=True, blank=True)
    symbol_operation = models.CharField(max_length=2, choices=OPERACIONES,null=True, blank=True)
    
    def __str__(self):
        return f"{self.simbolo} - {self.nombre}"




class ComentarioElemento(models.Model):
    elemento = models.ForeignKey(ElementoAnalisis, on_delete=models.CASCADE)
   
    comentario_verde = models.TextField(blank=True, null=True)
    comentario_amarillo = models.TextField(blank=True, null=True)
    comentario_rojo = models.TextField(blank=True, null=True)
    
    
    def __str__(self):
        return f"Comentarios para {self.elemento.nombre} en {self.categoria.nombre}"



#Calidad
class TiposCalidad(models.Model):
    is_c_1=models.BooleanField(default=False)
    is_c_2=models.BooleanField(default=False)
    nombre=models.CharField(max_length=255,blank=True, null=True)


class LimiteCalidad(models.Model):
    c1 = models.CharField(max_length=10,blank=True, null=True)  
    c2 = models.CharField(max_length=10,blank=True, null=True)  
    seq_espuma = models.CharField(max_length=20, blank=True, null=True)
   
    chispa = models.IntegerField(blank=True, null=True)
    valor=models.CharField(max_length=20, blank=True, null=True)
    

    def __str__(self):
        return f"Límites calidad {self.tipo} "
    
    
    
    
    
#Viscosidad
    
class TiposViscosidad(models.Model):
    is_v_1=models.BooleanField(default=False)
    is_v_2=models.BooleanField(default=False)
    nombre=models.CharField(max_length=255,blank=True, null=True)
class LimiteViscosidad(models.Model):
    v1 = models.CharField(max_length=20,blank=True, null=True)  # SAE, ISO, ATF, 2T
    v2= models.CharField(max_length=20,blank=True, null=True)  # SAE, ISO, ATF, 2T
    vmin = models.FloatField(blank=True, null=True)
    vmax = models.FloatField(blank=True, null=True)
    iv1 = models.IntegerField(blank=True, null=True)
    iv2 = models.IntegerField(blank=True, null=True)
    
    
    def __str__(self):
        return f"Límites viscosidad {self.tipo}"


class PruebaLimite(models.Model):

    prueba = models.OneToOneField(Prueba, on_delete=models.CASCADE, related_name='limite_asignado')

    # Polimorfismo controlado
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    limite = GenericForeignKey('content_type', 'object_id')

    def __str__(self):
        return f"{self.prueba.nombre} usa {self.content_type.name} ({self.object_id})"
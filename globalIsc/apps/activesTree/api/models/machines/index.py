from django.db import models
from apps.misc.api.models.companies.index import Empresa


class Maquina(models.Model):
    nombre = models.CharField(max_length=255)
    componente = models.CharField(max_length=255, blank=True, null=True)
    tipoAceite = models.CharField(max_length=255, blank=True, null=True)
    
    frecuenciaCambio = models.CharField(max_length=255, blank=True, null=True)
    frecuenciaAnalisis = models.CharField(max_length=255, blank=True, null=True)
    
    numero_serie = models.CharField(max_length=255, blank=True, null=True)
    
    codigo_equipo = models.CharField(max_length=255,  blank=True, null=True)
    empresa= models.ForeignKey(Empresa,on_delete=models.CASCADE,default='1')

    def __str__(self):
        return self.nombre






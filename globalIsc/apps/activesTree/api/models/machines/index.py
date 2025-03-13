from django.db import models
from apps.misc.api.models.companies.index import Empresa


class Maquina(models.Model):
    nombre = models.CharField(max_length=255)
    componente = models.CharField(max_length=255)
    tipoAceite = models.CharField(max_length=255, blank=True, null=True)
    
    frecuenciaCambio = models.CharField(max_length=255)
    frecuenciaAnalisis = models.CharField(max_length=255)
    
    numero_serie = models.CharField(max_length=255, blank=True, null=True)
    
    codigo_equipo = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.nombre






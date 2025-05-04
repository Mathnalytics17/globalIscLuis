from django.db import models
from apps.users.api.models.index import User
from django.core.validators import MinValueValidator
import uuid
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra


class Resultado(models.Model):
    ESTATUS_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('preliminar', 'Preliminar'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
    ]
    
    prueba_muestra = models.ForeignKey(PruebaMuestra, on_delete=models.CASCADE, related_name='resultados')
   
    resultado = models.FloatField()
    fecha_medicion = models.DateTimeField()
    usuario_medicion = models.ForeignKey(User, on_delete=models.PROTECT, related_name='resultados_medidos')
    estatus = models.CharField(max_length=20, choices=ESTATUS_CHOICES, default='pendiente')
    observaciones = models.TextField(blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Resultado {self.id} - {self.prueba_muestra.prueba.nombre}"

class HistoricoResultado(models.Model):
    resultado = models.ForeignKey(Resultado, on_delete=models.CASCADE, related_name='historico')
    resultado_anterior = models.FloatField()

    fecha_medicion_anterior = models.DateTimeField()
    usuario_medicion = models.ForeignKey(User, on_delete=models.PROTECT)
    observaciones_anterior = models.TextField(blank=True, null=True)
    usuario_modificacion = models.ForeignKey(User, on_delete=models.PROTECT, related_name='modificaciones_resultados')
    fecha_modificacion = models.DateTimeField(auto_now_add=True)
    motivo_cambio = models.TextField()
    
    def __str__(self):
        return f"Histórico {self.id} - Resultado {self.resultado.id}"

class RevisionResultado(models.Model):
    resultado = models.ForeignKey(Resultado, on_delete=models.CASCADE, related_name='revisiones')
    usuario_revision = models.ForeignKey(User, on_delete=models.PROTECT)
    estatus_anterior = models.CharField(max_length=20, blank=True, null=True)
    estatus_nuevo = models.CharField(max_length=20)
    observaciones = models.TextField(blank=True, null=True)
    fecha_revision = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Revisión {self.id} - Resultado {self.resultado.id}"

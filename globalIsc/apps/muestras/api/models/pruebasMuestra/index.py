from django.db import models
from apps.users.api.models.index import User
from django.core.validators import MinValueValidator
import uuid
from apps.muestras.api.models.muestras.index import Muestra
from apps.misc.api.models.pruebas.index import Prueba

class PruebaMuestra(models.Model):
    muestra = models.ForeignKey(Muestra, on_delete=models.CASCADE, related_name='pruebas')
    prueba = models.ForeignKey(Prueba, on_delete=models.PROTECT)
    usuario_solicitud = models.ForeignKey(User, on_delete=models.PROTECT)
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    completada = models.BooleanField(default=False)
    is_used=models.BooleanField(default=False)
    class Meta:
        unique_together = ('muestra', 'prueba')
    
    def __str__(self):
        return f"{self.muestra.id} - {self.prueba.nombre}"
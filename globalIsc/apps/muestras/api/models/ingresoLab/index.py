from django.db import models
from apps.users.api.models.index import User
from django.core.validators import MinValueValidator
import uuid
from apps.muestras.api.models.muestras.index import Muestra

class IngresoLab(models.Model):
    muestra = models.OneToOneField(Muestra, on_delete=models.CASCADE, related_name='ingreso_lab')
    fecha_recepcion = models.DateTimeField()
    usuario_recepcion = models.ForeignKey(User, on_delete=models.PROTECT)
    condiciones_entrega = models.TextField(blank=True, null=True)
    campos_adicionales = models.JSONField(blank=True, null=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Ingreso de {self.muestra.id}"
from django.db import models
from apps.muestras.api.models.muestras.index import Muestra
from apps.users.api.models.index import User
from apps.misc.api.models.limitesyaux.index import ElementoAnalisis
from django.utils import timezone

class Interpretacion(models.Model):
    muestra = models.OneToOneField(Muestra, on_delete=models.CASCADE, related_name='interpretacion')
    usuario = models.ForeignKey(User, on_delete=models.PROTECT)
    comentario_proveedor = models.TextField(blank=True, null=True)
    fecha_interpretacion = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Interpretación para {self.muestra.id}"

class DetalleInterpretacion(models.Model):
    NIVELES = [
        ('verde', 'Verde - Normal'),
        ('amarillo', 'Amarillo - Precaución'),
        ('rojo', 'Rojo - Peligro'),
    ]
    
    interpretacion = models.ForeignKey(Interpretacion, on_delete=models.CASCADE, related_name='detalles')
    elemento = models.ForeignKey(ElementoAnalisis, on_delete=models.PROTECT)
    resultado_obtenido = models.FloatField()
    nivel = models.CharField(max_length=10, choices=NIVELES)
    comentario_automatico = models.TextField(blank=True, null=True)
    comentario_manual = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = ('interpretacion', 'elemento')
    
    def __str__(self):
        return f"Detalle {self.elemento.simbolo} para {self.interpretacion.muestra.id}"

class Reporte(models.Model):
    ESTATUS_CHOICES = [
        ('borrador', 'Borrador'),
        ('pendiente_aprobacion', 'Pendiente de Aprobación'),
        ('aprobado', 'Aprobado'),
        ('enviado', 'Enviado'),
    ]
    
    consecutivo = models.CharField(max_length=20, unique=True)  # R20230001
    muestra = models.OneToOneField(Muestra, on_delete=models.CASCADE, related_name='reporte')
    fecha_emision = models.DateTimeField()
    usuario_emision = models.ForeignKey(User, on_delete=models.PROTECT, related_name='reportes_emitidos')
    usuario_aprobacion = models.ForeignKey(User, on_delete=models.PROTECT, related_name='reportes_aprobados', blank=True, null=True)
    fecha_aprobacion = models.DateTimeField(blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    ruta_archivo = models.CharField(max_length=255, blank=True, null=True)
    estatus = models.CharField(max_length=20, choices=ESTATUS_CHOICES, default='borrador')
    
    def __str__(self):
        return self.consecutivo
    
    def save(self, *args, **kwargs):
        if not self.consecutivo:
            # Generar consecutivo automático (ej: R20230001)
            last_reporte = Reporte.objects.order_by('-consecutivo').first()
            if last_reporte:
                last_num = int(last_reporte.consecutivo[5:])
                new_num = last_num + 1
            else:
                new_num = 1
            self.consecutivo = f"R{timezone.now().year}{str(new_num).zfill(4)}"
        super().save(*args, **kwargs)
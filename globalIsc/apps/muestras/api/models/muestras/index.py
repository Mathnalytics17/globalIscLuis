from django.db import models
from apps.users.api.models.index import User
from django.core.validators import MinValueValidator
import uuid
from apps.misc.api.models.lubricante.index import Lubricante
from apps.misc.api.models.tipoEquipo.index import TipoEquipo,ReferenciaEquipo
from apps.activesTree.api.models.machines.index import Maquina
from django.utils import timezone

class Muestra(models.Model):
    UNIDADES_PERIODO = [
        ('horas', 'Horas'),
        ('km', 'Kilómetros'),
        ('millas', 'Millas'),
        ('dias', 'Días'),
    ]
    
    id = models.CharField(max_length=20, primary_key=True)  # M20230001
    fecha_toma = models.DateTimeField()
    lubricante = models.ForeignKey(Lubricante, on_delete=models.PROTECT)
    Equipo = models.ForeignKey(Maquina, on_delete=models.PROTECT,default=1)
    contacto_cliente = models.CharField(max_length=100, blank=True, null=True)
    equipo_placa = models.CharField(max_length=50, blank=True, null=True)
    referencia_equipo = models.ForeignKey(ReferenciaEquipo, on_delete=models.PROTECT, blank=True, null=True)
    periodo_servicio_aceite = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    unidad_periodo_aceite = models.CharField(max_length=10, choices=UNIDADES_PERIODO, blank=True, null=True)
    periodo_servicio_equipo = models.FloatField(blank=True, null=True, validators=[MinValueValidator(0)])
    unidad_periodo_equipo = models.CharField(max_length=10, choices=UNIDADES_PERIODO, blank=True, null=True)
    observaciones = models.TextField(blank=True, null=True)
    campos_adicionales = models.JSONField(blank=True, null=True)
    usuario_registro = models.ForeignKey(User, on_delete=models.PROTECT)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    is_ingresado=models.BooleanField(default=False)
    is_aprobado=models.BooleanField(default=False)
    was_checked=models.DateField(default="2025-05-01")
    def __str__(self):
        return self.id
    
    def save(self, *args, **kwargs):
        if not self.id:
            # Generar ID automático (ej: M20230001)
            last_muestra = Muestra.objects.order_by('-id').first()
            if last_muestra:
                last_num = int(last_muestra.id[5:])
                new_num = last_num + 1
            else:
                new_num = 1
            self.id = f"M{timezone.now().year}{str(new_num).zfill(4)}"
        super().save(*args, **kwargs)

from django.db import models

from apps.activesTree.api.models.machines.index import Maquina


class AnalisisLubricante(models.Model):
    Maquina=models.ForeignKey(Maquina, on_delete=models.CASCADE, related_name="maquina")
    propietario = models.CharField(max_length=255)
    fecha_muestreo = models.DateField()
    nombre_equipo = models.CharField(max_length=255)
    modelo = models.CharField(max_length=255)
    horas_km_aceite = models.IntegerField()
    id_placa = models.CharField(max_length=255)
    lugar_trabajo = models.CharField(max_length=255)
    horas_km_equipo = models.IntegerField()
    ref_aceite = models.CharField(max_length=255)
    no_interno_lab = models.CharField(max_length=255, unique=True)
    fecha_recepcion = models.DateField()

    def __str__(self):
        return f"Análisis de {self.nombre_equipo} - {self.fecha_muestreo}"








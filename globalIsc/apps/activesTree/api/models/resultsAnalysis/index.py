from django.db import models
from apps.activesTree.api.models.analysis.index import AnalisisLubricante

class ResultadoMuestrasAceite(models.Model):
    analisis = models.ForeignKey(AnalisisLubricante, on_delete=models.CASCADE, related_name="resultados")
    observaciones = models.TextField()
    indicadores = models.CharField(max_length=255,default='NO REGISTRA')  # Para almacenar múltiples indicadores como un diccionario

    def __str__(self):
        return f"Resultados de {self.analisis.nombre_equipo} - {self.analisis.fecha_muestreo}"





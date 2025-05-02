from django.contrib import admin
from apps.reporte.api.models.index import Interpretacion, DetalleInterpretacion, Reporte

@admin.register(Interpretacion)
class InterpretacionAdmin(admin.ModelAdmin):
    pass

@admin.register(DetalleInterpretacion)
class DetalleInterpretacionAdmin(admin.ModelAdmin):
    pass

@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    pass
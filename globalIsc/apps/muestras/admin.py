from django.contrib import admin
from apps.muestras.api.models.muestras.index import Muestra
from apps.muestras.api.models.ingresoLab.index import IngresoLab
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra

@admin.register(Muestra)
class MuestraAdmin(admin.ModelAdmin):
    pass

@admin.register(IngresoLab)
class IngresoLabAdmin(admin.ModelAdmin):
   pass

@admin.register(PruebaMuestra)
class PruebaMuestraAdmin(admin.ModelAdmin):
    pass
from django.contrib import admin
from apps.muestras.api.models.muestras.index import HistorialMuestra, Muestra
from apps.muestras.api.models.pruebasMuestra.index import PruebaMuestra
from apps.muestras.api.models.loteMuestras.index import LoteMuestras
from apps.muestras.api.models.sampleBatchExcel.index import SampleBatchExcelTemplateToken
from apps.muestras.api.models.muestraAtributoTecnico.index import MuestraAtributoTecnico
@admin.register(Muestra)
class MuestraAdmin(admin.ModelAdmin):
    pass

@admin.register(HistorialMuestra)
class HistorialMuestraAdmin(admin.ModelAdmin):
    list_display = ("muestra", "accion", "usuario", "creado_en")
    list_filter = ("accion", "creado_en")
    search_fields = ("muestra__id", "usuario__email")
    readonly_fields = ("muestra", "accion", "usuario", "cambios", "estado_anterior", "estado_nuevo", "creado_en")

@admin.register(SampleBatchExcelTemplateToken)
class SampleBatchExcelTemplateTokenAdmin(admin.ModelAdmin):
    pass
@admin.register(PruebaMuestra)
class PruebaMuestraAdmin(admin.ModelAdmin):
    pass

@admin.register(LoteMuestras)
class LoteMuestrasAdmin(admin.ModelAdmin):
    pass

admin.site.register(MuestraAtributoTecnico)

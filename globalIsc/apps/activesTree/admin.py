from django.contrib import admin
from apps.activesTree.api.models.index import Carpeta
from apps.activesTree.api.models.analysis.index import AnalisisLubricante
from apps.activesTree.api.models.machines.index import Maquina
from apps.activesTree.api.models.resultsAnalysis.index import ResultadoMuestrasAceite

# Register your models here.


@admin.register(Carpeta)
class CarpetaAdmin(admin.ModelAdmin):
    pass


@admin.register(AnalisisLubricante)
class AnalisisLubricanteAdmin(admin.ModelAdmin):
    pass
@admin.register(Maquina)
class MaquinaAdmin(admin.ModelAdmin):
    pass

@admin.register(ResultadoMuestrasAceite)
class ResultadoMuestrasAceite(admin.ModelAdmin):
    pass

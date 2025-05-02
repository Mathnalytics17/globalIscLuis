from django.contrib import admin
from apps.resultado.api.models.index import Resultado, RevisionResultado, HistoricoResultado

@admin.register(Resultado)
class ResultadoAdmin(admin.ModelAdmin):
    pass

@admin.register(RevisionResultado)
class RevisionResultadoAdmin(admin.ModelAdmin):
    pass

@admin.register(HistoricoResultado)
class HistoricoResultadoAdmin(admin.ModelAdmin):
   pass
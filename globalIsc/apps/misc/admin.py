from django.contrib import admin

from apps.misc.api.models.pruebas.index import (
    Prueba,
    PruebaResultado,
    PruebaResultadoDivision,
    PruebaResultadoComponente,
    PruebaResultadoSeparador,
    PruebaResultadoDisposicion,
    PruebaResultadoDisposicionItem,
)
from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CatalogoTecnico,
    CampoTecnicoMuestra,
    CatalogoTecnicoCampo,
    CatalogoTecnicoItem,
    CatalogoTecnicoItemValor,
    PruebaFuenteLimite,
    CriterioEvaluacionLimite,
    PruebaLimiteCampo,
)


class PruebaResultadoInline(admin.TabularInline):
    model = PruebaResultado
    extra = 0


@admin.register(Prueba)
class PruebaAdmin(admin.ModelAdmin):
    list_display = ("acronimo", "nombre_variable", "metodo", "activo")
    list_filter = ("activo", "metodo")
    search_fields = ("acronimo", "nombre_variable", "condicion", "metodo__codigo", "metodo__nombre")
    inlines = [PruebaResultadoInline]


class PruebaResultadoDivisionInline(admin.TabularInline):
    model = PruebaResultadoDivision
    extra = 0


@admin.register(PruebaResultado)
class PruebaResultadoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "acronimo", "prueba", "activo")
    list_filter = ("activo", "prueba")
    search_fields = ("nombre", "acronimo", "prueba__acronimo", "prueba__nombre_variable")
    inlines = [PruebaResultadoDivisionInline]


class PruebaResultadoComponenteInline(admin.TabularInline):
    model = PruebaResultadoComponente
    extra = 0


class PruebaResultadoSeparadorInline(admin.TabularInline):
    model = PruebaResultadoSeparador
    extra = 0


class PruebaResultadoDisposicionInline(admin.TabularInline):
    model = PruebaResultadoDisposicion
    extra = 0


@admin.register(PruebaResultadoDivision)
class PruebaResultadoDivisionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "resultado", "es_principal", "activo")
    list_filter = ("activo", "es_principal")
    search_fields = ("nombre", "resultado__nombre", "resultado__prueba__acronimo")
    inlines = [PruebaResultadoComponenteInline, PruebaResultadoSeparadorInline, PruebaResultadoDisposicionInline]


class PruebaResultadoDisposicionItemInline(admin.TabularInline):
    model = PruebaResultadoDisposicionItem
    extra = 0


@admin.register(PruebaResultadoDisposicion)
class PruebaResultadoDisposicionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "division", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre", "division__nombre", "division__resultado__nombre")
    inlines = [PruebaResultadoDisposicionItemInline]


admin.site.register(PruebaResultadoComponente)
admin.site.register(PruebaResultadoSeparador)
admin.site.register(CatalogoTecnico)
admin.site.register(CampoTecnicoMuestra)
admin.site.register(CatalogoTecnicoCampo)
admin.site.register(CatalogoTecnicoItem)
admin.site.register(CatalogoTecnicoItemValor)
admin.site.register(PruebaFuenteLimite)
admin.site.register(CriterioEvaluacionLimite)
admin.site.register(PruebaLimiteCampo)

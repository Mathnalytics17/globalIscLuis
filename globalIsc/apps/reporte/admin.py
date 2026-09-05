from django.contrib import admin

from apps.reporte.api.models.index import Reporte, ReporteEnvio


@admin.register(Reporte)
class ReporteAdmin(admin.ModelAdmin):
    list_display = ("consecutivo", "version", "muestra", "lote", "estatus", "visible_cliente", "fecha_emision", "fecha_envio")
    list_filter = ("estatus", "visible_cliente", "fecha_emision", "fecha_envio")
    search_fields = ("consecutivo", "muestra__id", "lote__id", "lote__cliente_empresa__nombre")


@admin.register(ReporteEnvio)
class ReporteEnvioAdmin(admin.ModelAdmin):
    list_display = ("reporte", "canal", "destinatario_email", "destinatario_usuario", "estado", "fecha_envio")
    list_filter = ("canal", "estado", "fecha_envio")
    search_fields = ("reporte__consecutivo", "destinatario_email")

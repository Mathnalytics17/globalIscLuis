from django.contrib import admin
from apps.activesTree.api.models.index import Carpeta
from apps.activesTree.api.models.machines.index import Maquina

# Register your models here.


@admin.register(Carpeta)
class CarpetaAdmin(admin.ModelAdmin):
    pass


@admin.register(Maquina)
class MaquinaAdmin(admin.ModelAdmin):
    pass

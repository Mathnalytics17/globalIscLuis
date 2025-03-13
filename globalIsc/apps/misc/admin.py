from django.contrib import admin
from apps.misc.api.models.companies.index import Empresa
from apps.misc.api.models.roles.index import Rol

# Register your models here.

@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    pass

@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    pass

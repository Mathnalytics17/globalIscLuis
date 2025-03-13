from django.contrib import admin
from apps.users.api.models.index import Empresa,Rol,Usuario


# Register your models here.


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    pass
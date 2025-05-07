from django.contrib import admin
from apps.misc.api.models.companies.index import Empresa
from apps.misc.api.models.roles.index import Rol
from apps.misc.api.models.lubricante.index import Lubricante
from apps.misc.api.models.tipoEquipo.index import ReferenciaEquipo, TipoEquipo
from apps.misc.api.models.pruebas.index import Prueba
from apps.misc.api.models.limitesyaux.index import LimiteCalidad, LimiteElemento, LimiteViscosidad, CategoriaLimite
from apps.misc.api.models.more.index import Calidad,Color,ColorGrasa,Jabon,Marca,MarcaGrasa,NLGI,ComentarioPredefinido
# Configuración para Empresa
@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    pass

# Configuración para Rol
@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    pass
# Configuración para Lubricante
@admin.register(Lubricante)
class LubricanteAdmin(admin.ModelAdmin):
    pass

# Configuración para TipoEquipo
@admin.register(TipoEquipo)
class TipoEquipoAdmin(admin.ModelAdmin):
    pass

# Configuración para ReferenciaEquipo
@admin.register(ReferenciaEquipo)
class ReferenciaEquipoAdmin(admin.ModelAdmin):
    pass

# Configuración para Prueba
@admin.register(Prueba)
class PruebaAdmin(admin.ModelAdmin):
    pass


# Configuración para CategoriaLimite
@admin.register(CategoriaLimite)
class CategoriaLimiteAdmin(admin.ModelAdmin):
    pass

# Configuración para LimiteElemento
@admin.register(Calidad)
class CalidadAdmin(admin.ModelAdmin):
    pass

# Configuración para LimiteViscosidad
@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    pass

# Configuración para LimiteCalidad
@admin.register(ColorGrasa)
class ColorGrasaAdmin(admin.ModelAdmin):
    pass

@admin.register(Jabon)
class JabonAdmin(admin.ModelAdmin):
    pass
@admin.register(NLGI)
class NLGIdmin(admin.ModelAdmin):
    pass
@admin.register(MarcaGrasa)
class MarcaGrasaAdmin(admin.ModelAdmin):
    pass
@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    pass

@admin.register(ComentarioPredefinido)
class ComentarioPredefinidoAdmin(admin.ModelAdmin):
    pass
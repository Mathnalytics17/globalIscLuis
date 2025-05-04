from .companies.index import EmpresaViewSet
from .roles.index import RolViewSet
from .limitesyaux.index import (
    ElementoAnalisisViewSet,
    CategoriaLimiteViewSet,
    LimiteElementoViewSet,
    ComentarioElementoViewSet,
    LimiteViscosidadViewSet,
    LimiteCalidadViewSet
)
from .lubricante.index import LubricanteViewSet
from .pruebas.index import PruebaViewSet, EquipoLaboratorioViewSet
from .tipoEquipo.index import TipoEquipoViewSet, ReferenciaEquipoViewSet

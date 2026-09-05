from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission

from apps.misc.api.models.technicalCatalogs.index import (
    Condicion,
    EquipoPrueba,
    MetodoEquipo,
    Unidad,
)
from apps.misc.api.serializers.technicalCatalogs.index import (
    CondicionSerializer,
    EquipoPruebaSerializer,
    MetodoEquipoSerializer,
    UnidadSerializer,
)


class BaseTechnicalCatalogViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    ordering_fields = ["nombre", "codigo", "created_at", "updated_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        activo = self.request.query_params.get("activo")

        if activo is not None:
            queryset = queryset.filter(activo=activo.lower() in ["1", "true", "yes"])

        return queryset


class EquipoPruebaViewSet(BaseTechnicalCatalogViewSet):
    permission_action_map = {
        "list": "equipos_prueba.ver",
        "retrieve": "equipos_prueba.ver",
        "create": "equipos_prueba.crear",
        "update": "equipos_prueba.editar",
        "partial_update": "equipos_prueba.editar",
        "destroy": "equipos_prueba.eliminar",
    }
    queryset = EquipoPrueba.objects.all()
    serializer_class = EquipoPruebaSerializer
    search_fields = ["codigo", "nombre", "descripcion"]


class UnidadViewSet(BaseTechnicalCatalogViewSet):
    permission_action_map = {
        "list": "unidades.ver",
        "retrieve": "unidades.ver",
        "create": "unidades.crear",
        "update": "unidades.editar",
        "partial_update": "unidades.editar",
        "destroy": "unidades.eliminar",
    }
    queryset = Unidad.objects.all()
    serializer_class = UnidadSerializer
    search_fields = ["nombre", "simbolo", "magnitud", "descripcion"]


class MetodoEquipoViewSet(BaseTechnicalCatalogViewSet):
    permission_action_map = {
        "list": "equipos_prueba.ver",
        "retrieve": "equipos_prueba.ver",
        "create": "equipos_prueba.crear",
        "update": "equipos_prueba.editar",
        "partial_update": "equipos_prueba.editar",
        "destroy": "equipos_prueba.eliminar",
    }
    queryset = MetodoEquipo.objects.select_related("equipo_prueba")
    serializer_class = MetodoEquipoSerializer
    search_fields = ["codigo", "nombre", "norma_referencia", "descripcion"]

    def get_queryset(self):
        queryset = super().get_queryset()
        equipo_prueba = self.request.query_params.get("equipo_prueba")

        if equipo_prueba:
            queryset = queryset.filter(equipo_prueba_id=equipo_prueba)

        return queryset


class CondicionViewSet(BaseTechnicalCatalogViewSet):
    permission_action_map = {
        "list": "condiciones.ver",
        "retrieve": "condiciones.ver",
        "create": "condiciones.crear",
        "update": "condiciones.editar",
        "partial_update": "condiciones.editar",
        "destroy": "condiciones.eliminar",
    }
    queryset = Condicion.objects.select_related("unidad")
    serializer_class = CondicionSerializer
    search_fields = ["nombre", "magnitud", "descripcion", "unidad__simbolo"]

    def get_queryset(self):
        queryset = super().get_queryset()
        magnitud = self.request.query_params.get("magnitud")

        if magnitud:
            queryset = queryset.filter(magnitud=magnitud)

        return queryset

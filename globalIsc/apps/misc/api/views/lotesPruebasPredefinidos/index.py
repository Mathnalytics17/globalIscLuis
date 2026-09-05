from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.utils.pagination import StandardResultsSetPagination
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission

from apps.misc.api.models.lotesPruebasPredefinidos.index import LotePruebasPredefinido
from apps.misc.api.serializers.lotesPruebasPredefinidos.index import (
    LotePruebasPredefinidoListSerializer,
    LotePruebasPredefinidoSerializer,
)


class LotePruebasPredefinidoViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    pagination_class = StandardResultsSetPagination
    queryset = LotePruebasPredefinido.objects.select_related("tipo_gestion")
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {
        "list": "lotes_predefinidos.ver",
        "retrieve": "lotes_predefinidos.ver",
        "create": "lotes_predefinidos.crear",
        "update": "lotes_predefinidos.editar",
        "partial_update": "lotes_predefinidos.editar",
        "destroy": "lotes_predefinidos.eliminar",
        "restore": "lotes_predefinidos.editar",
    }
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["nombre", "descripcion", "tipo_gestion__nombre"]
    ordering_fields = ["nombre", "updated_at", "created_at"]

    def get_queryset(self):
        queryset = super().get_queryset()
        activo = self.request.query_params.get("activo")
        tipo_gestion = self.request.query_params.get("tipo_gestion")
        tipo_lote = self.request.query_params.get("tipo_lote")

        if self.action == "restore":
            pass
        elif activo is None:
            queryset = queryset.filter(activo=True)
        else:
            queryset = queryset.filter(activo=activo.lower() in ["1", "true", "yes"])

        if tipo_gestion:
            queryset = queryset.filter(tipo_gestion_id=tipo_gestion)
        if tipo_lote:
            queryset = queryset.filter(tipo_lote=tipo_lote)

        return queryset.prefetch_related(
            "detalles__prueba",
            "detalles__equipo_prueba",
            "detalles__metodo_equipo__equipo_prueba",
            "detalles__condicion__unidad",
        )

    def get_serializer_class(self):
        if self.action == "list":
            return LotePruebasPredefinidoListSerializer
        return LotePruebasPredefinidoSerializer

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        instance = self.get_object()
        instance.activo = True
        instance.deleted_at = None
        instance.save(update_fields=["activo", "deleted_at", "updated_at"])
        serializer = LotePruebasPredefinidoSerializer(instance, context=self.get_serializer_context())
        return Response(serializer.data)

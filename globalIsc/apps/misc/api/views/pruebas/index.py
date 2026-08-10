from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.utils.pagination import StandardResultsSetPagination
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission

from apps.misc.api.models.pruebas.index import Prueba
from apps.misc.api.serializers.pruebas.index import (
    PruebaListSerializer,
    PruebaDetailSerializer,
    PruebaCreateUpdateSerializer,
)


class PruebaViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    pagination_class = StandardResultsSetPagination
    queryset = Prueba.objects.all()
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {
        "list": "pruebas.ver",
        "retrieve": "pruebas.ver",
        "create": "pruebas.crear",
        "update": "pruebas.editar",
        "partial_update": "pruebas.editar",
        "destroy": "pruebas.eliminar",
        "restore": "pruebas.restaurar",
    }

    def get_queryset(self):
        queryset = (
            Prueba.objects.all()
            .select_related("metodo", "metodo__equipo_prueba", "unidad_catalogo", "condicion_catalogo", "condicion_catalogo__unidad")
            .prefetch_related(
                "resultados",
                "resultados__unidad_catalogo",
                "resultados__divisiones",
                "resultados__divisiones__componentes",
                "resultados__divisiones__separadores",
                "resultados__divisiones__disposiciones",
                "resultados__divisiones__disposiciones__items",
            )
            .order_by("-id")
        )

        # Para restaurar necesitamos poder encontrar pruebas inactivas
        if self.action == "restore":
            return queryset

        include_inactive = self.request.query_params.get("include_inactive")

        if include_inactive in ["true", "1", "yes"]:
            return queryset

        return queryset.filter(activo=True)

    def get_serializer_class(self):
        if self.action == "list":
            include_structure = str(
                self.request.query_params.get("include_structure", "")
            ).strip().lower()
            if include_structure in {"1", "true", "yes"}:
                return PruebaDetailSerializer
            return PruebaListSerializer

        if self.action in ["create", "update", "partial_update"]:
            return PruebaCreateUpdateSerializer

        return PruebaDetailSerializer

    def destroy(self, request, *args, **kwargs):
        prueba = self.get_object()
        prueba.activo = False
        prueba.save(update_fields=["activo"])
        return Response(
            {"detail": "Prueba eliminada correctamente."},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def restore(self, request, pk=None):
        prueba = Prueba.objects.filter(pk=pk).first()

        if not prueba:
            return Response(
                {"detail": "La prueba no existe."},
                status=status.HTTP_404_NOT_FOUND,
            )

        prueba.activo = True
        prueba.save(update_fields=["activo"])

        serializer = PruebaDetailSerializer(prueba, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

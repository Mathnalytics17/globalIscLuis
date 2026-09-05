from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission
from apps.users.api.models.index import User

from apps.muestras.api.models.muestraAtributoTecnico.index import MuestraAtributoTecnico
from apps.muestras.api.serializers.muestraAtributoTecnico.index import (
    MuestraAtributoTecnicoSerializer,
)


class MuestraAtributoTecnicoViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {
        "list": "muestras.ver",
        "retrieve": "muestras.ver",
        "create": "muestras.editar_atributos_tecnicos",
        "update": "muestras.editar_atributos_tecnicos",
        "partial_update": "muestras.editar_atributos_tecnicos",
        "destroy": "muestras.editar_atributos_tecnicos",
    }
    serializer_class = MuestraAtributoTecnicoSerializer

    def get_queryset(self):
        queryset = MuestraAtributoTecnico.objects.select_related(
            "muestra",
            "catalogo",
            "item",
        )
        muestra = self.request.query_params.get("muestra")
        catalogo = self.request.query_params.get("catalogo")
        if muestra:
            queryset = queryset.filter(muestra_id=muestra)
        if catalogo:
            queryset = queryset.filter(catalogo_id=catalogo)
        user = self.request.user
        if not (user.is_superuser or user.role == User.Role.GLOBAL):
            queryset = queryset.filter(muestra__lote__cliente_empresa=user.empresa)
        return queryset

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

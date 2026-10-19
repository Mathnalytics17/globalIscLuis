from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from apps.muestras.api.models.importaciones import CorridaImportacion
from apps.muestras.api.serializers.importaciones import CorridaImportacionSerializer
from apps.users.api.models.index import User
from apps.users.api.data_scope import scope_queryset
from apps.utils.pagination import StandardResultsSetPagination
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission


class CorridaImportacionViewSet(ActionPermissionMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = CorridaImportacionSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {"list": "importaciones.ver", "retrieve": "importaciones.ver"}

    def get_queryset(self):
        queryset = CorridaImportacion.objects.select_related("empresa", "actor")
        queryset = scope_queryset(queryset, self.request.user, "empresa_id")
        for key, lookup in {"empresa": "empresa_id", "estado": "estado", "tipo": "tipo"}.items():
            if self.request.query_params.get(key):
                queryset = queryset.filter(**{lookup: self.request.query_params[key]})
        return queryset

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from apps.muestras.api.models.importaciones import CorridaImportacion
from apps.muestras.api.serializers.importaciones import CorridaImportacionSerializer
from apps.users.api.models.index import User
from apps.utils.pagination import StandardResultsSetPagination
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission


class CorridaImportacionViewSet(ActionPermissionMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = CorridaImportacionSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {"list": "dashboard.ver_empresa", "retrieve": "dashboard.ver_empresa"}

    def get_queryset(self):
        queryset = CorridaImportacion.objects.select_related("empresa", "actor")
        user = self.request.user
        if not (user.is_superuser or user.role == User.Role.GLOBAL):
            queryset = queryset.filter(empresa_id=getattr(user, "empresa_id", None))
        for key, lookup in {"empresa": "empresa_id", "estado": "estado", "tipo": "tipo"}.items():
            if self.request.query_params.get(key):
                queryset = queryset.filter(**{lookup: self.request.query_params[key]})
        return queryset

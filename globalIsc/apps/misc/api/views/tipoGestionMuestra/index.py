from django.db.models import Q
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission

from apps.misc.api.models.tipoGestionMuestra.index import TipoGestionMuestra
from apps.misc.api.serializers.tipoGestionMuestra.index import TipoGestionMuestraSerializer
from apps.users.api.models.index import User


class TipoGestionMuestraViewSet(ActionPermissionMixin, viewsets.ModelViewSet):
    serializer_class = TipoGestionMuestraSerializer
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {
        "list": "tipos_gestion.ver",
        "retrieve": "tipos_gestion.ver",
        "create": "tipos_gestion.crear",
        "update": "tipos_gestion.editar",
        "partial_update": "tipos_gestion.editar",
        "destroy": "tipos_gestion.eliminar",
        "restore": "tipos_gestion.editar",
    }

    def get_queryset(self):
        queryset = TipoGestionMuestra.objects.prefetch_related(
            "empresas_permitidas",
            "pruebas_sugeridas",
        ).all()

        incluir_eliminados = self.request.query_params.get("incluir_eliminados")
        empresa_id = self.request.query_params.get("empresa_id")
        search = self.request.query_params.get("search")
        user = self.request.user

        if incluir_eliminados != "true":
            queryset = queryset.filter(deleted_at__isnull=True)

        if search:
            queryset = queryset.filter(nombre__icontains=search)

        can_view_all = user.is_superuser or user.role == User.Role.GLOBAL or not user.empresa_id
        effective_company_id = empresa_id if can_view_all else user.empresa_id
        if effective_company_id:
            queryset = queryset.filter(
                Q(aplica_a_todos=True) |
                Q(empresas_permitidas__id=effective_company_id)
            ).distinct()

        return queryset

    def perform_destroy(self, instance):
        instance.activo = False
        instance.deleted_at = timezone.now()
        instance.save(update_fields=["activo", "deleted_at", "updated_at"])

    @action(detail=True, methods=["post"], url_path="restore")
    def restore(self, request, pk=None):
        instance = self.get_object()
        instance.activo = True
        instance.deleted_at = None
        instance.save(update_fields=["activo", "deleted_at", "updated_at"])

        serializer = self.get_serializer(instance)
        return Response(serializer.data, status=status.HTTP_200_OK)

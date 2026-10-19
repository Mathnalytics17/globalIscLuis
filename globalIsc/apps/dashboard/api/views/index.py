from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission

from apps.dashboard.api.services.operational_center import build_operational_center
from apps.users.api.models.index import User


class OperationalCenterViewSet(ActionPermissionMixin, viewsets.ViewSet):
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {"list": "dashboard.ver_global"}

    def list(self, request):
        # El centro operativo consolida datos de toda la operación. No basta
        # con ocultar el enlace: solo Global Oil puede consultar este endpoint.
        if not (request.user.is_superuser or request.user.role == User.Role.GLOBAL):
            raise PermissionDenied("El Dashboard operativo está disponible solo para Global Oil.")
        return Response(build_operational_center(request.user, request.query_params))


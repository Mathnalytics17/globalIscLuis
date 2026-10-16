from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from permissions import ActionPermissionMixin, DenyReadOnlyWrite, HasSecurityPermission

from apps.dashboard.api.services.operational_center import build_operational_center


class OperationalCenterViewSet(ActionPermissionMixin, viewsets.ViewSet):
    permission_classes = [IsAuthenticated, DenyReadOnlyWrite, HasSecurityPermission]
    permission_action_map = {"list": "dashboard.ver_empresa"}

    def list(self, request):
        return Response(build_operational_center(request.user, request.query_params))


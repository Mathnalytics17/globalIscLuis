from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.misc.api.serializers.companies.index import EmpresaSerializer
from apps.misc.api.models.companies.index import Empresa
from apps.users.api.models.index import SecurityRole, User
from apps.users.api.services import audit_user_action, create_invitation, user_has_permission


class EmpresaViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = Empresa.objects.prefetch_related("user_set").all().order_by("nombre")
    serializer_class = EmpresaSerializer

    def _is_global(self):
        user = self.request.user
        return bool(user and user.is_authenticated and (user.is_superuser or user.role == User.Role.GLOBAL))

    def _has_company_permission(self, code):
        return self._is_global() or user_has_permission(self.request.user, code)

    def _require_company_permission(self, code):
        if not self._has_company_permission(code):
            self.permission_denied(self.request, message="No tiene permisos para esta accion.")

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.role == User.Role.GLOBAL:
            return queryset
        return queryset.filter(id=user.empresa_id)

    def list(self, request, *args, **kwargs):
        self._require_company_permission("empresas.ver")
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        self._require_company_permission("empresas.ver")
        return super().retrieve(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        self._require_company_permission("empresas.crear")
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        admin_email = serializer.validated_data.pop("admin_email", None)
        admin_role_id = serializer.validated_data.pop("admin_role", None)
        transfer_existing_admin = serializer.validated_data.pop("transfer_existing_admin", False)
        invitation = None

        try:
            with transaction.atomic():
                empresa = serializer.save()

                if admin_email:
                    role = (
                        SecurityRole.objects.filter(id=admin_role_id).first()
                        if admin_role_id
                        else SecurityRole.objects.filter(code="admin_empresa").first()
                    )
                    invitation = create_invitation(
                        email=admin_email,
                        empresa=empresa,
                        role=role,
                        is_company_admin=True,
                        invited_by=request.user,
                        allow_company_transfer=bool(transfer_existing_admin and self._is_global()),
                    )
        except ValueError as exc:
            return Response({"admin_email": [str(exc)]}, status=status.HTTP_400_BAD_REQUEST)

        audit_user_action(request, "companies.create", empresa=empresa, detail=f"Empresa creada: {empresa.nombre}")
        response_data = self.get_serializer(empresa).data
        if invitation is not None:
            response_data["admin_invitation"] = {
                "id": invitation.id,
                "email": invitation.email,
                "email_sent": bool(getattr(invitation, "email_sent", False)),
                "delivery_status": (invitation.metadata or {}).get("email_delivery", {}).get("status", "pending"),
                "message": getattr(invitation, "email_error", "") or "Invitación enviada correctamente.",
            }
        return Response(response_data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        self._require_company_permission("empresas.editar")
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        self._require_company_permission("empresas.editar")
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        self._require_company_permission("empresas.eliminar")
        empresa = self.get_object()
        empresa.is_active = False
        empresa.status = Empresa.Status.INACTIVE
        empresa.save(update_fields=["is_active", "status"])
        audit_user_action(request, "companies.disable", empresa=empresa, detail=f"Empresa desactivada: {empresa.nombre}")
        return Response({"message": "Empresa desactivada correctamente"}, status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"])
    def estadisticas(self, request):
        self._require_company_permission("empresas.ver")
        queryset = self.get_queryset()
        total_empresas = queryset.count()
        last_company = queryset.order_by("-fecha_creacion").first()
        return Response({
            "total_empresas": total_empresas,
            "ultima_empresa_creada": last_company.nombre if last_company else None,
        })

    @action(detail=True, methods=["get"])
    def informacion_completa(self, request, pk=None):
        self._require_company_permission("empresas.ver")
        empresa = self.get_object()
        return Response(self.get_serializer(empresa).data)

    @action(detail=False, methods=["get"])
    def buscar(self, request):
        self._require_company_permission("empresas.ver")
        nombre = request.query_params.get("nombre", "")
        if not nombre:
            return Response({"error": "Parametro 'nombre' requerido"}, status=status.HTTP_400_BAD_REQUEST)
        empresas = self.get_queryset().filter(nombre__icontains=nombre)
        return Response(self.get_serializer(empresas, many=True).data)

    @action(detail=True, methods=["post"], url_path="block")
    def block(self, request, pk=None):
        self._require_company_permission("empresas.bloquear")
        empresa = self.get_object()
        empresa.is_active = False
        empresa.status = Empresa.Status.BLOCKED
        empresa.blocked_at = timezone.now()
        empresa.block_reason = request.data.get("reason", "")
        empresa.save(update_fields=["is_active", "status", "blocked_at", "block_reason"])
        audit_user_action(request, "companies.block", empresa=empresa, detail=empresa.block_reason)
        return Response(self.get_serializer(empresa).data)

    @action(detail=True, methods=["post"], url_path="read-only")
    def read_only(self, request, pk=None):
        self._require_company_permission("empresas.modo_solo_lectura")
        empresa = self.get_object()
        empresa.is_active = True
        empresa.status = Empresa.Status.READ_ONLY
        empresa.read_only_until = request.data.get("read_only_until") or empresa.read_only_until
        empresa.retention_until = request.data.get("retention_until") or empresa.retention_until
        empresa.save(update_fields=["is_active", "status", "read_only_until", "retention_until"])
        audit_user_action(request, "companies.read_only", empresa=empresa)
        return Response(self.get_serializer(empresa).data)

    @action(detail=True, methods=["post"], url_path="restore-active")
    def restore_active(self, request, pk=None):
        self._require_company_permission("empresas.editar")
        empresa = self.get_object()
        empresa.is_active = True
        empresa.status = Empresa.Status.ACTIVE
        empresa.blocked_at = None
        empresa.block_reason = ""
        empresa.save(update_fields=["is_active", "status", "blocked_at", "block_reason"])
        audit_user_action(request, "companies.restore_active", empresa=empresa)
        return Response(self.get_serializer(empresa).data)

    @action(detail=True, methods=["post"], url_path="invite-admin")
    def invite_admin(self, request, pk=None):
        self._require_company_permission("usuarios.invitar")
        empresa = self.get_object()
        email = request.data.get("email") or empresa.email
        if not email:
            return Response({"email": "El correo es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
        role_id = request.data.get("role")
        role = (
            SecurityRole.objects.filter(id=role_id).first()
            if role_id
            else SecurityRole.objects.filter(code="admin_empresa").first()
        )
        try:
            invitation = create_invitation(
                email=email,
                empresa=empresa,
                role=role,
                is_company_admin=True,
                invited_by=request.user,
                allow_company_transfer=(
                    str(request.data.get("transfer_existing", "")).lower() in {"1", "true", "yes"}
                    and self._is_global()
                ),
            )
        except ValueError as exc:
            return Response(
                {
                    "email": [str(exc)],
                    "code": "existing_user_conflict",
                    "can_transfer": self._is_global(),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        audit_user_action(
            request,
            "companies.invite_admin",
            empresa=empresa,
            detail=f"Admin invitado: {email}",
            metadata={"invitation_id": invitation.id},
        )
        return Response({"status": "Invitacion enviada", "invitation_id": invitation.id})

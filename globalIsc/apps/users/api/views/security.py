from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.users.api.models.index import (
    SecurityPermission,
    SecurityRole,
    User,
    UserAuditLog,
    UserCompanyProfile,
    UserInvitation,
)
from apps.users.api.serializers.index import (
    SecurityPermissionSerializer,
    SecurityRoleSerializer,
    UserAuditLogSerializer,
    UserBlockSerializer,
    UserCompanyProfileSerializer,
    UserInvitationAcceptSerializer,
    UserInvitationSerializer,
    UserInviteCreateSerializer,
    UserSerializer,
)
from apps.users.api.services import (
    accept_invitation,
    audit_user_action,
    create_invitation,
    seed_default_permissions,
    send_invitation_email,
    user_has_permission,
    is_role_assignable_by,
)


class GlobalOrPermissionMixin:
    required_permission = None

    def _is_global(self):
        user = self.request.user
        return bool(user and user.is_authenticated and (user.is_superuser or user.role == User.Role.GLOBAL))

    def _has_required_permission(self, permission_code=None):
        if self._is_global():
            return True
        return user_has_permission(self.request.user, permission_code or self.required_permission)

    def check_security_permission(self, permission_code=None):
        if not self._has_required_permission(permission_code):
            self.permission_denied(self.request, message="No tiene permisos para esta accion.")


class SecurityPermissionViewSet(GlobalOrPermissionMixin, viewsets.ReadOnlyModelViewSet):
    queryset = SecurityPermission.objects.all().order_by("module", "action")
    serializer_class = SecurityPermissionSerializer
    permission_classes = [IsAuthenticated]
    required_permission = "permisos.ver_matriz"
    filterset_fields = ["module", "active"]
    search_fields = ["module", "action", "code", "description"]

    def list(self, request, *args, **kwargs):
        self.check_security_permission("permisos.ver_matriz")
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=["post"], url_path="seed-defaults")
    def seed_defaults(self, request):
        self.check_security_permission("permisos.editar_matriz")
        seed_default_permissions()
        audit_user_action(request, "permissions.seed_defaults", detail="Permisos base sincronizados")
        return Response({"status": "Permisos base sincronizados"})


class SecurityRoleViewSet(GlobalOrPermissionMixin, viewsets.ModelViewSet):
    queryset = SecurityRole.objects.prefetch_related("role_permissions__permission").all()
    serializer_class = SecurityRoleSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["scope", "active", "editable"]
    search_fields = ["name", "code", "description"]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self._is_global():
            return queryset
        # Admins de empresa solo necesitan ver roles asignables de empresa.
        return queryset.filter(scope=SecurityRole.Scope.COMPANY, active=True)

    permission_by_action = {
        "list": "roles.ver",
        "retrieve": "roles.ver",
        "create": "roles.crear",
        "update": "roles.editar",
        "partial_update": "roles.editar",
        "destroy": "roles.eliminar",
        "assignable": "usuarios.invitar",
        "matrix": "permisos.ver_matriz",
        "update_matrix": "permisos.editar_matriz",
    }

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.check_security_permission(self.permission_by_action.get(self.action, "roles.ver"))

    def perform_create(self, serializer):
        if not self._is_global():
            self.permission_denied(self.request, message="Solo GlobalOil puede crear roles.")
        role = serializer.save()
        audit_user_action(self.request, "roles.create", detail=f"Rol creado: {role.code}", metadata={"role_id": role.id})

    def perform_update(self, serializer):
        if not self._is_global():
            self.permission_denied(self.request, message="Solo GlobalOil puede editar roles.")
        role = serializer.save()
        audit_user_action(self.request, "roles.update", detail=f"Rol actualizado: {role.code}", metadata={"role_id": role.id})

    def destroy(self, request, *args, **kwargs):
        if not self._is_global():
            self.permission_denied(request, message="Solo GlobalOil puede desactivar roles.")
        role = self.get_object()
        if not role.editable:
            return Response({"detail": "Este rol no es editable."}, status=status.HTTP_400_BAD_REQUEST)
        role.active = False
        role.save(update_fields=["active", "updated_at"])
        audit_user_action(request, "roles.disable", detail=f"Rol desactivado: {role.code}", metadata={"role_id": role.id})
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=["get"], url_path="assignable")
    def assignable(self, request):
        roles = self.get_queryset().filter(active=True)
        roles = [role for role in roles if is_role_assignable_by(request.user, role)]
        return Response(SecurityRoleSerializer(roles, many=True).data)

    @action(detail=False, methods=["get"], url_path="matrix")
    def matrix(self, request):
        if not self._is_global():
            self.permission_denied(request, message="Solo GlobalOil puede ver la matriz global de permisos.")
        roles = SecurityRole.objects.prefetch_related("role_permissions__permission").filter(active=True)
        permissions = SecurityPermission.objects.filter(active=True).order_by("module", "action")
        return Response({
            "roles": SecurityRoleSerializer(roles, many=True).data,
            "permissions": SecurityPermissionSerializer(permissions, many=True).data,
        })

    @action(detail=True, methods=["put", "patch"], url_path="matrix")
    def update_matrix(self, request, pk=None):
        if not self._is_global():
            self.permission_denied(request, message="Solo GlobalOil puede editar la matriz de permisos.")
        role = self.get_object()
        serializer = self.get_serializer(role, data={"permission_codes": request.data.get("permission_codes", [])}, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        audit_user_action(request, "roles.update_matrix", detail=f"Matriz actualizada: {role.code}", metadata={"role_id": role.id})
        return Response(self.get_serializer(role).data)


class UserCompanyProfileViewSet(GlobalOrPermissionMixin, viewsets.ModelViewSet):
    serializer_class = UserCompanyProfileSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["empresa", "status", "is_company_admin", "role"]
    search_fields = ["user__email", "user__first_name", "user__last_name", "empresa__nombre"]

    def get_queryset(self):
        queryset = UserCompanyProfile.objects.select_related("user", "empresa", "role").all()
        user = self.request.user
        if user.is_superuser or user.role == User.Role.GLOBAL:
            return queryset
        return queryset.filter(empresa=user.empresa)

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        permission = "empresas.ver_usuarios" if self.action in ["list", "retrieve"] else "usuarios.asignar_roles"
        self.check_security_permission(permission)

    def _validate_assignable_role(self, role):
        if role and not is_role_assignable_by(self.request.user, role):
            self.permission_denied(self.request, message="No puede asignar roles GlobalOil o internos.")

    def perform_create(self, serializer):
        role = serializer.validated_data.get("role")
        empresa = serializer.validated_data.get("empresa")
        if not self._is_global() and empresa_id_mismatch(self.request.user, empresa):
            self.permission_denied(self.request, message="No puede crear perfiles en otra empresa.")
        self._validate_assignable_role(role)
        profile = serializer.save()
        audit_user_action(self.request, "users.profile_create", target_user=profile.user, empresa=profile.empresa, metadata={"profile_id": profile.id})

    def perform_update(self, serializer):
        role = serializer.validated_data.get("role", getattr(serializer.instance, "role", None))
        empresa = serializer.validated_data.get("empresa", getattr(serializer.instance, "empresa", None))
        if not self._is_global() and empresa_id_mismatch(self.request.user, empresa):
            self.permission_denied(self.request, message="No puede editar perfiles de otra empresa.")
        self._validate_assignable_role(role)
        profile = serializer.save()
        audit_user_action(self.request, "users.profile_update", target_user=profile.user, empresa=profile.empresa, metadata={"profile_id": profile.id})


class UserInvitationViewSet(GlobalOrPermissionMixin, viewsets.ModelViewSet):
    serializer_class = UserInvitationSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["empresa", "status", "is_company_admin", "role"]
    search_fields = ["email", "empresa__nombre"]

    def get_permissions(self):
        if self.action in ["accept", "validate_invitation"]:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = UserInvitation.objects.select_related("empresa", "role", "user", "invited_by").all()
        user = self.request.user
        if user.is_superuser or user.role == User.Role.GLOBAL:
            return queryset
        return queryset.filter(empresa=user.empresa)

    def create(self, request, *args, **kwargs):
        self.check_security_permission("usuarios.invitar")
        serializer = UserInviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        empresa = serializer.validated_data.get("empresa")
        if self._is_global() and empresa is None:
            return Response({"empresa": ["Este campo es requerido."]}, status=status.HTTP_400_BAD_REQUEST)
        if not self._is_global():
            empresa = request.user.empresa
            if empresa is None:
                return Response({"detail": "Su usuario no tiene empresa asociada."}, status=status.HTTP_400_BAD_REQUEST)
        if not self._is_global() and empresa_id_mismatch(request.user, empresa):
            return Response({"detail": "No puede invitar usuarios a otra empresa."}, status=status.HTTP_403_FORBIDDEN)
        role = serializer.validated_data.get("role")
        if not is_role_assignable_by(request.user, role):
            return Response({"detail": "No puede asignar roles GlobalOil o internos."}, status=status.HTTP_403_FORBIDDEN)
        try:
            invitation = create_invitation(
                email=serializer.validated_data["email"],
                empresa=empresa,
                role=role,
                is_company_admin=serializer.validated_data.get("is_company_admin", False),
                invited_by=request.user,
                metadata={
                    "first_name": serializer.validated_data.get("first_name", ""),
                    "last_name": serializer.validated_data.get("last_name", ""),
                },
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        audit_user_action(request, "users.invite", empresa=empresa, detail=f"Invitacion enviada a {invitation.email}", metadata={"invitation_id": invitation.id})
        return Response(UserInvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="resend")
    def resend(self, request, pk=None):
        self.check_security_permission("usuarios.reenviar_invitacion")
        old_invitation = self.get_object()
        if not is_role_assignable_by(request.user, old_invitation.role):
            return Response({"detail": "No puede reenviar invitaciones con roles GlobalOil o internos."}, status=status.HTTP_403_FORBIDDEN)
        old_invitation.status = UserInvitation.Status.REVOKED
        old_invitation.revoked_at = timezone.now()
        old_invitation.save(update_fields=["status", "revoked_at", "updated_at"])
        invitation = create_invitation(
            email=old_invitation.email,
            empresa=old_invitation.empresa,
            role=old_invitation.role,
            is_company_admin=old_invitation.is_company_admin,
            invited_by=request.user,
            metadata=old_invitation.metadata,
        )
        audit_user_action(request, "users.invitation_resend", empresa=invitation.empresa, detail=f"Invitacion reenviada a {invitation.email}", metadata={"old_id": old_invitation.id, "new_id": invitation.id})
        return Response(UserInvitationSerializer(invitation).data)

    @action(detail=True, methods=["post"], url_path="revoke")
    def revoke(self, request, pk=None):
        self.check_security_permission("usuarios.reenviar_invitacion")
        invitation = self.get_object()
        invitation.status = UserInvitation.Status.REVOKED
        invitation.revoked_at = timezone.now()
        invitation.save(update_fields=["status", "revoked_at", "updated_at"])
        audit_user_action(request, "users.invitation_revoke", empresa=invitation.empresa, detail=f"Invitacion revocada: {invitation.email}", metadata={"invitation_id": invitation.id})
        return Response(UserInvitationSerializer(invitation).data)

    @action(detail=False, methods=["post"], url_path="accept", permission_classes=[AllowAny])
    def accept(self, request):
        serializer = UserInvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = accept_invitation(
                token=serializer.validated_data["token"],
                first_name=serializer.validated_data["first_name"],
                last_name=serializer.validated_data["last_name"],
                phone=serializer.validated_data.get("phone", ""),
                avatar=serializer.validated_data.get("avatar"),
                password=serializer.validated_data["password"],
            )
        except (UserInvitation.DoesNotExist, ValueError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        audit_user_action(request, "users.invitation_accept", target_user=user, empresa=user.empresa, detail="Invitacion aceptada")
        return Response(UserSerializer(user).data)

    @action(detail=False, methods=["get"], url_path="validate", permission_classes=[AllowAny])
    def validate_invitation(self, request):
        token = request.query_params.get("token")
        if not token:
            return Response({"detail": "Token requerido."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            invitation = UserInvitation.objects.select_related("empresa", "role").get(token=token)
        except (UserInvitation.DoesNotExist, ValueError):
            return Response({"detail": "La invitacion no existe."}, status=status.HTTP_404_NOT_FOUND)

        if not invitation.is_valid():
            return Response({"detail": "La invitacion no es valida o ya expiro."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "email": invitation.email,
            "empresa": invitation.empresa_id,
            "empresa_nombre": getattr(invitation.empresa, "nombre", ""),
            "role": invitation.role_id,
            "role_name": getattr(invitation.role, "name", ""),
            "is_company_admin": invitation.is_company_admin,
            "expires_at": invitation.expires_at,
            "status": invitation.status,
            "metadata": invitation.metadata or {},
        })


class UserSecurityViewSet(GlobalOrPermissionMixin, viewsets.GenericViewSet):
    queryset = User.objects.select_related("empresa").all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.role == User.Role.GLOBAL:
            return queryset
        return queryset.filter(empresa=user.empresa)

    @action(detail=True, methods=["post"], url_path="block")
    def block(self, request, pk=None):
        self.check_security_permission("usuarios.bloquear")
        target = self.get_object()
        serializer = UserBlockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if target == request.user:
            return Response({"detail": "No puede bloquear su propia cuenta."}, status=status.HTTP_400_BAD_REQUEST)
        reason = serializer.validated_data.get("reason", "")
        scope = User.BlockScope.GLOBAL if self._is_global() else User.BlockScope.COMPANY
        target.is_active = False
        target.access_status = User.AccessStatus.BLOCKED
        target.blocked_at = timezone.now()
        target.blocked_by = request.user
        target.block_reason = reason
        target.block_scope = scope
        target.save(update_fields=["is_active", "access_status", "blocked_at", "blocked_by", "block_reason", "block_scope"])
        profiles = UserCompanyProfile.objects.filter(user=target)
        if not self._is_global():
            profiles = profiles.filter(empresa=request.user.empresa)
        profiles.update(status=UserCompanyProfile.Status.BLOCKED, blocked_at=timezone.now(), block_reason=reason)
        audit_user_action(request, "users.block", target_user=target, detail=reason, metadata={"scope": scope})
        return Response(UserSerializer(target).data)

    @action(detail=True, methods=["post"], url_path="unblock")
    def unblock(self, request, pk=None):
        self.check_security_permission("usuarios.desbloquear")
        target = self.get_object()
        if target.block_scope == User.BlockScope.GLOBAL and not self._is_global():
            return Response({"detail": "Solo GlobalOil puede desbloquear un bloqueo global."}, status=status.HTTP_403_FORBIDDEN)
        target.is_active = True
        target.access_status = User.AccessStatus.ACTIVE
        target.blocked_at = None
        target.blocked_by = None
        target.block_reason = ""
        target.block_scope = User.BlockScope.NONE
        target.save(update_fields=["is_active", "access_status", "blocked_at", "blocked_by", "block_reason", "block_scope"])
        profiles = UserCompanyProfile.objects.filter(user=target)
        if not self._is_global():
            profiles = profiles.filter(empresa=request.user.empresa)
        profiles.update(status=UserCompanyProfile.Status.ACTIVE, blocked_at=None, block_reason="")
        audit_user_action(request, "users.unblock", target_user=target)
        return Response(UserSerializer(target).data)

    @action(detail=True, methods=["post"], url_path="read-only")
    def read_only(self, request, pk=None):
        self.check_security_permission("usuarios.bloquear")
        target = self.get_object()
        target.is_active = True
        target.is_read_only = True
        target.access_status = User.AccessStatus.READ_ONLY
        target.block_scope = User.BlockScope.GLOBAL if self._is_global() else User.BlockScope.COMPANY
        target.save(update_fields=["is_active", "is_read_only", "access_status", "block_scope"])
        profiles = UserCompanyProfile.objects.filter(user=target)
        if not self._is_global():
            profiles = profiles.filter(empresa=request.user.empresa)
        profiles.update(status=UserCompanyProfile.Status.READ_ONLY)
        audit_user_action(request, "users.read_only", target_user=target, metadata={"scope": target.block_scope})
        return Response(UserSerializer(target).data)

    @action(detail=True, methods=["post"], url_path="restore-write")
    def restore_write(self, request, pk=None):
        self.check_security_permission("usuarios.desbloquear")
        target = self.get_object()
        if target.block_scope == User.BlockScope.GLOBAL and not self._is_global():
            return Response({"detail": "Solo GlobalOil puede restaurar escritura de un bloqueo global."}, status=status.HTTP_403_FORBIDDEN)
        target.is_read_only = False
        target.access_status = User.AccessStatus.ACTIVE
        target.block_scope = User.BlockScope.NONE
        target.save(update_fields=["is_read_only", "access_status", "block_scope"])
        profiles = UserCompanyProfile.objects.filter(user=target)
        if not self._is_global():
            profiles = profiles.filter(empresa=request.user.empresa)
        profiles.update(status=UserCompanyProfile.Status.ACTIVE)
        audit_user_action(request, "users.restore_write", target_user=target)
        return Response(UserSerializer(target).data)


class UserAuditLogViewSet(GlobalOrPermissionMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = UserAuditLogSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["empresa", "actor", "target_user", "module", "action"]
    search_fields = ["action", "detail", "actor__email", "target_user__email", "empresa__nombre"]

    def get_queryset(self):
        queryset = UserAuditLog.objects.select_related("actor", "target_user", "empresa").all()
        user = self.request.user
        if user.is_superuser or user.role == User.Role.GLOBAL:
            return queryset
        return queryset.filter(Q(empresa=user.empresa) | Q(actor=user) | Q(target_user=user))

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.check_security_permission("usuarios.ver_auditoria")


def empresa_id_mismatch(user, empresa):
    return getattr(user, "empresa_id", None) != getattr(empresa, "id", None)

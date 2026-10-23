# serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core import exceptions
from apps.users.api.models.index  import (
    EmailVerificationToken,
    PasswordResetToken,
    SecurityPermission,
    SecurityRole,
    SecurityRolePermission,
    UserAuditLog,
    UserCompanyProfile,
    UserDataScopeCompany,
    UserInvitation,
)
from apps.misc.api.models.companies.index import Empresa
from apps.users.api.data_scope import effective_data_scope
import uuid
from datetime import datetime, timedelta
from django.conf import settings
from rest_framework import serializers
from django.core.mail import send_mail
from rest_framework import serializers
from django.contrib.auth import get_user_model

import uuid
from django.utils import timezone
from datetime import timedelta
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

# Una preferencia de inicio nunca debe ser un redireccionamiento arbitrario.
ALLOWED_HOME_PATHS = {
    "", "/dashboard", "/activesTree", "/machines", "/muestras/lotes",
    "/muestras/nuevo-lote", "/muestras/laboratorio", "/muestras/resultados",
    "/muestras/revision-resultados", "/muestras/interpretacion", "/reportes",
}

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'password', 'password2', 'first_name', 'last_name', 'phone']
        extra_kwargs = {
            'password': {'write_only': True},
            'password2': {'write_only': True},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})

        try:
            validate_password(attrs['password'])
        except exceptions.ValidationError as e:
            raise serializers.ValidationError({'password': list(e.messages)})

        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user

class UserSerializer(serializers.ModelSerializer):
    empresa = serializers.StringRelatedField(read_only=True)  # Solo el string representation
    empresa_id = serializers.IntegerField(source='empresa.id', read_only=True)
    full_name = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()
    effective_data_scope = serializers.SerializerMethodField()
    assigned_company_ids = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name', 'role', 'phone', 'home_path', 'data_scope_override',
            'is_active', 'is_superuser', 'email_verified', 'empresa', 'empresa_id', 'access_status',
            'is_read_only', 'blocked_at', 'blocked_by', 'block_reason', 'block_scope',
            'last_login', 'permissions', 'profile', 'effective_data_scope', 'assigned_company_ids', 'firma_predeterminada',
        ]
        read_only_fields = ['id', 'email', 'is_active', 'is_superuser', 'email_verified', 'empresa', 'data_scope_override']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.email

    def get_effective_data_scope(self, obj):
        return effective_data_scope(obj)

    def get_assigned_company_ids(self, obj):
        return list(obj.data_scope_companies.values_list("empresa_id", flat=True))

    def validate_home_path(self, value):
        value = str(value or "").strip()
        if value not in ALLOWED_HOME_PATHS:
            raise serializers.ValidationError("Seleccione una página de inicio válida.")
        return value

    def validate_firma_predeterminada(self, value):
        if value is None:
            return value
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("La firma no puede superar 2 MB.")
        content_type = getattr(value, "content_type", "")
        if content_type not in ["image/png", "image/jpeg"]:
            raise serializers.ValidationError("La firma debe ser una imagen PNG o JPG.")
        return value

    def get_permissions(self, obj):
        # Permisos efectivos, deduplicados, solo por perfiles activos o solo lectura.
        return list(
            SecurityPermission.objects.filter(
                permission_roles__role__user_profiles__user=obj,
                permission_roles__role__user_profiles__status__in=[
                    UserCompanyProfile.Status.ACTIVE,
                    UserCompanyProfile.Status.READ_ONLY,
                ],
                permission_roles__allowed=True,
                active=True,
            ).values_list("code", flat=True).distinct().order_by("code")
        )

    def get_profile(self, obj):
        profiles = obj.company_profiles.select_related("empresa", "role")
        # The editable role must belong to the user's current company.  A user
        # can retain historical profiles (including a removed profile after a
        # transfer), and selecting an arbitrary active one made the editor and
        # reinvitation send the company/role of an old membership.
        profile = profiles.filter(empresa_id=obj.empresa_id).order_by("-updated_at", "-id").first()
        if profile is None:
            profile = (
                profiles
                .filter(status__in=[
                    UserCompanyProfile.Status.PENDING,
                    UserCompanyProfile.Status.ACTIVE,
                    UserCompanyProfile.Status.READ_ONLY,
                    UserCompanyProfile.Status.BLOCKED,
                ])
                .order_by("-is_company_admin", "-updated_at", "-id")
                .first()
            )
        if not profile:
            return None
        return {
            "id": profile.id,
            # Keep both the explicit *_id values and the conventional relation
            # keys.  Browser clients use the latter when editing a profile.
            "empresa": profile.empresa_id,
            "empresa_id": profile.empresa_id,
            "empresa_nombre": getattr(profile.empresa, "nombre", None),
            "role": profile.role_id,
            "role_id": profile.role_id,
            "role_name": getattr(profile.role, "name", None),
            "role_code": getattr(profile.role, "code", None),
            "role_scope": getattr(profile.role, "scope", None),
            "role_default_home_path": getattr(profile.role, "default_home_path", ""),
            "role_data_scope": getattr(profile.role, "data_scope", "OWN_COMPANY"),
            "is_company_admin": profile.is_company_admin,
            "status": profile.status,
        }


# En tu serializers.py
class UserDetailSerializer(serializers.ModelSerializer):
    empresa = serializers.StringRelatedField(read_only=True)  # Solo lectura para mostrar
    empresa_id = serializers.PrimaryKeyRelatedField(
        queryset=Empresa.objects.all(), 
        source='empresa', 
        write_only=True,
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'is_active', 'role', 'email_verified', 'date_joined', 
                 'empresa', 'empresa_id', 'phone', 'home_path', 'data_scope_override', 'access_status',
                 'is_read_only', 'blocked_at', 'blocked_by', 'block_reason', 'block_scope',
                 'firma_predeterminada']
        extra_kwargs = {
            'password': {'write_only': True},
            'date_joined': {'read_only': True},
            # Roles are assigned exclusively through guarded company profiles.
            'role': {'read_only': True},
        }

    def validate(self, attrs):
        request = self.context.get("request")
        if request and self.instance and request.user == self.instance:
            protected_fields = {
                "is_active", "email_verified", "access_status", "is_read_only",
                "blocked_at", "blocked_by", "block_reason", "block_scope",
            }
            attempted = protected_fields.intersection(attrs)
            if attempted:
                raise serializers.ValidationError({
                    field: "Este campo solo puede cambiarlo un administrador autorizado."
                    for field in attempted
                })
        return attrs

    def validate_home_path(self, value):
        value = str(value or "").strip()
        if value not in ALLOWED_HOME_PATHS:
            raise serializers.ValidationError("Seleccione una página de inicio válida.")
        return value

    def update(self, instance, validated_data):
        # Evitar que se actualice el username y bloquear cambio de empresa.
        # Si un usuario cambia de empresa, se debe crear una cuenta nueva y dejar la anterior inactiva
        # para conservar trazabilidad histórica.
        validated_data.pop('username', None)
        new_empresa = validated_data.get('empresa')
        if new_empresa is not None and getattr(instance, 'empresa_id', None) != getattr(new_empresa, 'id', None):
            raise serializers.ValidationError({
                'empresa_id': 'No se permite cambiar la empresa de un usuario. Cree un usuario nuevo y desactive el anterior.'
            })
        validated_data.pop('empresa', None)
        return super().update(instance, validated_data)

    def validate_firma_predeterminada(self, value):
        if value is None:
            return value
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("La firma no puede superar 2 MB.")
        content_type = getattr(value, "content_type", "")
        if content_type not in ["image/png", "image/jpeg"]:
            raise serializers.ValidationError("La firma debe ser una imagen PNG o JPG.")
        return value
    
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True)
    new_password2 = serializers.CharField(required=True)

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password2']:
            raise serializers.ValidationError({"new_password": "Password fields didn't match."})

        try:
            validate_password(attrs['new_password'])
        except exceptions.ValidationError as e:
            raise serializers.ValidationError({'new_password': list(e.messages)})

        return attrs

class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.UUIDField()



User = get_user_model()

class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def create(self, validated_data):
        user = User.objects.filter(email=validated_data['email']).first()
        if user is None:
            return {'message': 'Si la cuenta existe, recibirá instrucciones de recuperación.'}

        PasswordResetToken.objects.filter(user=user).delete()
        token = PasswordResetToken.objects.create(
            user=user,
            expires_at=timezone.now() + timedelta(
                hours=settings.PASSWORD_RESET_TOKEN_EXPIRY_HOURS
            ),
        )
        try:
            self.send_reset_email(user, token)
        except Exception:
            logger.exception("No se pudo enviar el correo de recuperación")
        return {'message': 'Si la cuenta existe, recibirá instrucciones de recuperación.'}

    def send_reset_email(self, user, token):
        reset_url = f"{settings.FRONTEND_URL}users/resetPassword?token={token.token}"
        subject = "Restablece tu contraseña"
        message = f"""Hola {user.get_full_name() or user.email},

Solicitaste restablecer tu contraseña. Abre este enlace:
{reset_url}

El enlace expirará en {settings.PASSWORD_RESET_TOKEN_EXPIRY_HOURS} horas.
Si no lo solicitaste, ignora este correo.
"""
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
        logger.info("Correo de recuperación solicitado para el usuario %s", user.pk)
class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(min_length=8, write_only=True)
    new_password2 = serializers.CharField(min_length=8, write_only=True)

    def validate(self, data):
        # Validar formato UUID
        try:
            uuid.UUID(data['token'])
        except ValueError:
            raise serializers.ValidationError({
                'token': 'Formato de token inválido'
            })
        
        # Validar coincidencia de contraseñas
        if data['new_password'] != data['new_password2']:
            raise serializers.ValidationError({
                'new_password2': 'Las contraseñas no coinciden'
            })
            
        return data


class SecurityPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityPermission
        fields = ["id", "module", "action", "code", "description", "active", "created_at"]
        read_only_fields = ["id", "code", "created_at"]


class SecurityRolePermissionSerializer(serializers.ModelSerializer):
    permission_code = serializers.CharField(source="permission.code", read_only=True)
    permission_module = serializers.CharField(source="permission.module", read_only=True)
    permission_action = serializers.CharField(source="permission.action", read_only=True)

    class Meta:
        model = SecurityRolePermission
        fields = [
            "id", "role", "permission", "permission_code", "permission_module",
            "permission_action", "allowed", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class SecurityRoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()
    permission_codes = serializers.ListField(
        child=serializers.CharField(),
        write_only=True,
        required=False,
    )

    class Meta:
        model = SecurityRole
        fields = [
            "id", "name", "code", "scope", "description", "default_home_path", "data_scope", "editable", "active",
            "legacy_role", "permissions", "permission_codes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_default_home_path(self, value):
        value = str(value or "").strip()
        if value not in ALLOWED_HOME_PATHS:
            raise serializers.ValidationError("Seleccione una página de inicio válida.")
        return value

    def validate(self, attrs):
        default_home = attrs.get("default_home_path", getattr(self.instance, "default_home_path", ""))
        scope = attrs.get("scope", getattr(self.instance, "scope", None))
        if default_home == "/dashboard" and scope != SecurityRole.Scope.GLOBAL:
            raise serializers.ValidationError({"default_home_path": "El Dashboard operativo solo se puede asignar a roles Global Oil."})
        data_scope = attrs.get("data_scope", getattr(self.instance, "data_scope", SecurityRole.DataScope.OWN_COMPANY))
        if scope == SecurityRole.Scope.GLOBAL and data_scope != SecurityRole.DataScope.ALL_COMPANIES:
            raise serializers.ValidationError({"data_scope": "Los roles Global Oil deben tener alcance sobre todas las empresas."})
        return attrs

    def get_permissions(self, obj):
        return list(
            SecurityPermission.objects.filter(
                permission_roles__role=obj,
                permission_roles__allowed=True,
                active=True,
            ).values("id", "module", "action", "code", "description").order_by("module", "action")
        )

    def _sync_permissions(self, role, permission_codes):
        permissions = SecurityPermission.objects.filter(code__in=permission_codes, active=True)
        found_codes = set(permissions.values_list("code", flat=True))
        missing = sorted(set(permission_codes) - found_codes)
        if missing:
            raise serializers.ValidationError({"permission_codes": f"Permisos inexistentes: {', '.join(missing)}"})

        SecurityRolePermission.objects.filter(role=role).exclude(permission__in=permissions).update(allowed=False)
        for permission in permissions:
            SecurityRolePermission.objects.update_or_create(
                role=role,
                permission=permission,
                defaults={"allowed": True},
            )

    def create(self, validated_data):
        permission_codes = validated_data.pop("permission_codes", None)
        role = super().create(validated_data)
        if permission_codes is not None:
            self._sync_permissions(role, permission_codes)
        return role

    def update(self, instance, validated_data):
        permission_codes = validated_data.pop("permission_codes", None)
        role = super().update(instance, validated_data)
        if permission_codes is not None:
            self._sync_permissions(role, permission_codes)
        return role


class UserCompanyProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source="user.email", read_only=True)
    empresa_nombre = serializers.CharField(source="empresa.nombre", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)
    role_code = serializers.CharField(source="role.code", read_only=True)
    role_data_scope = serializers.CharField(source="role.data_scope", read_only=True)

    class Meta:
        model = UserCompanyProfile
        fields = [
            "id", "user", "user_email", "empresa", "empresa_nombre", "role",
            "role_name", "role_code", "role_data_scope", "is_company_admin", "status",
            "activated_at", "blocked_at", "block_reason", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class UserDataScopeCompanySerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source="empresa.nombre", read_only=True)
    user_email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = UserDataScopeCompany
        fields = ["id", "user", "user_email", "empresa", "empresa_nombre", "assigned_by", "created_at"]
        read_only_fields = ["id", "assigned_by", "created_at"]


class UserInvitationSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source="empresa.nombre", read_only=True)
    role_name = serializers.CharField(source="role.name", read_only=True)
    invited_by_email = serializers.EmailField(source="invited_by.email", read_only=True)

    class Meta:
        model = UserInvitation
        fields = [
            "id", "email", "empresa", "empresa_nombre", "role", "role_name",
            "user", "status", "is_company_admin", "invited_by",
            "invited_by_email", "accepted_at", "revoked_at", "expires_at",
            "created_at", "updated_at", "metadata",
        ]
        read_only_fields = [
            "id", "user", "status", "invited_by", "accepted_at",
            "revoked_at", "created_at", "updated_at",
        ]


class UserInviteCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    empresa = serializers.PrimaryKeyRelatedField(queryset=Empresa.objects.all(), required=False, allow_null=True)
    role = serializers.PrimaryKeyRelatedField(queryset=SecurityRole.objects.filter(active=True), required=False, allow_null=True)
    is_company_admin = serializers.BooleanField(default=False)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    transfer_existing = serializers.BooleanField(default=False, required=False)


class UserInvitationAcceptSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    avatar = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    password2 = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def validate(self, attrs):
        password = attrs.get("password", "")
        password2 = attrs.get("password2", "")
        if bool(password) != bool(password2) or password != password2:
            raise serializers.ValidationError({"password2": "Las contrasenas no coinciden."})
        if password:
            try:
                validate_password(password)
            except exceptions.ValidationError as exc:
                raise serializers.ValidationError({"password": list(exc.messages)})
        return attrs


class UserBlockSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)
    read_only = serializers.BooleanField(default=False)


class UserAuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True)
    target_user_email = serializers.EmailField(source="target_user.email", read_only=True)
    empresa_nombre = serializers.CharField(source="empresa.nombre", read_only=True)
    actor_nombre = serializers.SerializerMethodField()
    target_user_nombre = serializers.SerializerMethodField()
    empresa_efectiva_id = serializers.SerializerMethodField()
    empresa_efectiva_nombre = serializers.SerializerMethodField()

    class Meta:
        model = UserAuditLog
        fields = [
            "id", "actor", "actor_email", "target_user", "target_user_email",
            "empresa", "empresa_nombre", "empresa_efectiva_id", "empresa_efectiva_nombre",
            "actor_nombre", "target_user_nombre", "action", "module", "detail",
            "metadata", "ip_address", "user_agent", "created_at",
        ]
        read_only_fields = fields

    @staticmethod
    def _display_name(user):
        if not user:
            return ""
        return user.get_full_name() or user.email or str(user.pk)

    def get_actor_nombre(self, obj):
        # Login events have no authenticated actor yet; the target account is
        # the meaningful person to display in that situation.
        return self._display_name(obj.actor or obj.target_user) or "Sistema"

    def get_target_user_nombre(self, obj):
        return self._display_name(obj.target_user)

    @staticmethod
    def _effective_company(obj):
        return obj.empresa or getattr(obj.actor, "empresa", None) or getattr(obj.target_user, "empresa", None)

    def get_empresa_efectiva_id(self, obj):
        company = self._effective_company(obj)
        return company.id if company else None

    def get_empresa_efectiva_nombre(self, obj):
        company = self._effective_company(obj)
        return company.nombre if company else "Global / sin empresa asignada"

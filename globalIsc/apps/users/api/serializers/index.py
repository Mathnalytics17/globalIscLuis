# serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core import exceptions
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from apps.users.api.models.index  import (
    EmailVerificationToken,
    PasswordResetToken,
    SecurityPermission,
    SecurityRole,
    SecurityRolePermission,
    UserAuditLog,
    UserCompanyProfile,
    UserInvitation,
)
from apps.misc.api.models.companies.index import Empresa
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

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims
        token['email'] = user.email
        token['role'] = user.role
        token['is_active'] = user.is_active
        token['email_verified'] = user.email_verified
        
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        
        if not self.user.is_active:
            raise serializers.ValidationError("User account is not active.")
            
        return data

class UserSerializer(serializers.ModelSerializer):
    empresa = serializers.StringRelatedField(read_only=True)  # Solo el string representation
    empresa_id = serializers.IntegerField(source='empresa.id', read_only=True)
    full_name = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name', 'role', 'phone',
            'is_active', 'is_superuser', 'email_verified', 'empresa', 'empresa_id', 'access_status',
            'is_read_only', 'blocked_at', 'blocked_by', 'block_reason', 'block_scope',
            'permissions', 'profile', 'firma_predeterminada',
        ]
        read_only_fields = ['id', 'email', 'is_active', 'is_superuser', 'email_verified', 'empresa']

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.email

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
        profile = (
            obj.company_profiles
            .select_related("empresa", "role")
            .filter(status__in=[
                UserCompanyProfile.Status.PENDING,
                UserCompanyProfile.Status.ACTIVE,
                UserCompanyProfile.Status.READ_ONLY,
                UserCompanyProfile.Status.BLOCKED,
            ])
            .order_by("-is_company_admin", "id")
            .first()
        )
        if not profile:
            return None
        return {
            "id": profile.id,
            "empresa_id": profile.empresa_id,
            "empresa_nombre": getattr(profile.empresa, "nombre", None),
            "role_id": profile.role_id,
            "role_name": getattr(profile.role, "name", None),
            "role_code": getattr(profile.role, "code", None),
            "role_scope": getattr(profile.role, "scope", None),
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
                 'empresa', 'empresa_id', 'phone', 'access_status',
                 'is_read_only', 'blocked_at', 'blocked_by', 'block_reason', 'block_scope',
                 'firma_predeterminada']
        extra_kwargs = {
            'password': {'write_only': True},
            'date_joined': {'read_only': True}
        }

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
    
    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No existe un usuario con este email")
        return value

    def create(self, validated_data):
        user = User.objects.get(email=validated_data['email'])
        
        # Invalidar tokens previos
        PasswordResetToken.objects.filter(user=user).delete()
        
        # Crear nuevo token
        token = PasswordResetToken.objects.create(
            user=user,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        # Aquí deberías enviar el email (implementar esta parte)
        self.send_reset_email(user, token)
        
        return {'message': 'Se ha enviado un email con instrucciones'}

    def send_reset_email(self, user, token):
         # Eliminar tokens previos si existen
            PasswordResetToken.objects.filter(user=user).delete()
            
            expires_at = timezone.now() + timedelta(days=settings.EMAIL_VERIFICATION_TOKEN_EXPIRY_DAYS)
            token = PasswordResetToken.objects.create(
                user=user,
                expires_at=expires_at
            )
            reset_url = f"{settings.FRONTEND_URL}users/resetPassword?token={token.token}"
           
            subject = "Cambia tu password"
            message = f"""
            Hola {user.get_full_name() or user.email},
            
            Por favor haz clic en el siguiente enlace para verificar tu correo:
            { reset_url}
            
            Este enlace expirará en {settings.EMAIL_VERIFICATION_TOKEN_EXPIRY_DAYS} días.
            
            Si no solicitaste este registro, ignora este mensaje.
            """
            
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )
            
            logger.info("Email de recuperación enviado a %s", user.email)
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
            "id", "name", "code", "scope", "description", "editable", "active",
            "legacy_role", "permissions", "permission_codes", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

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

    class Meta:
        model = UserCompanyProfile
        fields = [
            "id", "user", "user_email", "empresa", "empresa_nombre", "role",
            "role_name", "role_code", "is_company_admin", "status",
            "activated_at", "blocked_at", "block_reason", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


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


class UserInvitationAcceptSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    avatar = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["password2"]:
            raise serializers.ValidationError({"password2": "Las contrasenas no coinciden."})
        try:
            validate_password(attrs["password"])
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

    class Meta:
        model = UserAuditLog
        fields = [
            "id", "actor", "actor_email", "target_user", "target_user_email",
            "empresa", "empresa_nombre", "action", "module", "detail",
            "metadata", "ip_address", "user_agent", "created_at",
        ]
        read_only_fields = fields

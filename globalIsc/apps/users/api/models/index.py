# models.py
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.mail import send_mail
from django.conf import settings
import uuid
    
from django.db import models
from django.contrib.auth import get_user_model
from apps.misc.api.models.companies.index import Empresa
class CustomUserManager(BaseUserManager):
    """Define a model manager for User model with no username field."""

    def _create_user(self, email, password=None, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError('The Email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)

class User(AbstractUser):
    class Role(models.TextChoices):
        GLOBAL= "GLOBAL", "GlobalOil"
        ADMIN = "ADMINISTRADOR", "Administrador"
        EMPRESA = "EMPRESA", "Empresa"
        LABORATORISTA = "LABORATORISTA", "Laboratorista"
        OPERARIO = "OPERARIO", "Operario"

    class AccessStatus(models.TextChoices):
        PENDING_INVITATION = "PENDING_INVITATION", "Pendiente invitacion"
        ACTIVE = "ACTIVE", "Activo"
        BLOCKED = "BLOCKED", "Bloqueado"
        READ_ONLY = "READ_ONLY", "Solo lectura"
        DISABLED = "DISABLED", "Deshabilitado"

    class BlockScope(models.TextChoices):
        NONE = "NONE", "Sin bloqueo"
        GLOBAL = "GLOBAL", "Bloqueo GlobalOil"
        COMPANY = "COMPANY", "Bloqueo empresa"

    username = None
    email = models.EmailField(_('email address'), unique=True)
    
    # User status fields
    is_active = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    
    # Role field
    role = models.CharField(max_length=50, choices=Role.choices, default=Role.OPERARIO)
    
    # Additional fields
    phone = models.CharField(max_length=20, blank=True)
    
    avatar = models.CharField(max_length=255, blank=True, null=True)
    firma_predeterminada = models.ImageField(
        upload_to="firmas_usuarios/",
        blank=True,
        null=True,
    )
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    # Empresa principal. Para usuarios internos de GlobalOil puede ser nula;
    # los usuarios externos deben tener empresa por validación de invitación/perfil.
    empresa = models.ForeignKey(Empresa, null=True, blank=True, on_delete=models.SET_NULL)
    access_status = models.CharField(
        max_length=30,
        choices=AccessStatus.choices,
        default=AccessStatus.PENDING_INVITATION,
        db_index=True,
    )
    is_read_only = models.BooleanField(default=False)
    blocked_at = models.DateTimeField(null=True, blank=True)
    blocked_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="blocked_users",
    )
    block_reason = models.TextField(blank=True)
    block_scope = models.CharField(
        max_length=20,
        choices=BlockScope.choices,
        default=BlockScope.NONE,
        db_index=True,
    )
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        """
        Sobrescribe el método save para crear automáticamente
        un fundraiser cuando se crea un usuario COMERCIAL
        """
        is_new = not self.pk  # Verifica si es un nuevo usuario (no tiene ID aún)
        
        # Guarda primero el usuario
        super().save(*args, **kwargs)
        
    def email_user(self, subject, message, from_email=None, **kwargs):
        """Send an email to this user."""
        send_mail(subject, message, from_email, [self.email], **kwargs)

class EmailVerificationToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_valid(self):
        from django.utils import timezone
        return timezone.now() < self.expires_at

class PasswordResetToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def is_valid(self):
        from django.utils import timezone
        return timezone.now() < self.expires_at


class SecurityRole(models.Model):
    class Scope(models.TextChoices):
        GLOBAL = "GLOBAL", "GlobalOil"
        COMPANY = "COMPANY", "Empresa"
        INTERNAL = "INTERNAL", "Interno"

    name = models.CharField(max_length=120)
    code = models.SlugField(max_length=80, unique=True)
    scope = models.CharField(max_length=20, choices=Scope.choices, default=Scope.COMPANY)
    description = models.TextField(blank=True)
    editable = models.BooleanField(default=True)
    active = models.BooleanField(default=True, db_index=True)
    legacy_role = models.CharField(max_length=50, choices=User.Role.choices, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scope", "name"]
        indexes = [
            models.Index(fields=["scope", "active"]),
        ]

    def __str__(self):
        return self.name


class SecurityPermission(models.Model):
    module = models.CharField(max_length=80, db_index=True)
    action = models.CharField(max_length=80)
    code = models.SlugField(max_length=140, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["module", "action"]
        unique_together = ("module", "action")
        indexes = [
            models.Index(fields=["module", "active"]),
        ]

    def __str__(self):
        return self.code


class SecurityRolePermission(models.Model):
    role = models.ForeignKey(SecurityRole, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey(SecurityPermission, on_delete=models.CASCADE, related_name="permission_roles")
    allowed = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("role", "permission")
        indexes = [
            models.Index(fields=["role", "allowed"]),
            models.Index(fields=["permission", "allowed"]),
        ]

    def __str__(self):
        return f"{self.role.code}:{self.permission.code}={self.allowed}"


class UserCompanyProfile(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        ACTIVE = "ACTIVE", "Activo"
        BLOCKED = "BLOCKED", "Bloqueado"
        READ_ONLY = "READ_ONLY", "Solo lectura"
        REMOVED = "REMOVED", "Removido"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="company_profiles")
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="user_profiles")
    role = models.ForeignKey(SecurityRole, null=True, blank=True, on_delete=models.SET_NULL, related_name="user_profiles")
    is_company_admin = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    blocked_at = models.DateTimeField(null=True, blank=True)
    block_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("user", "empresa")
        indexes = [
            models.Index(fields=["empresa", "status"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.empresa.nombre}"


class UserInvitation(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendiente"
        ACCEPTED = "ACCEPTED", "Aceptada"
        EXPIRED = "EXPIRED", "Expirada"
        REVOKED = "REVOKED", "Revocada"

    email = models.EmailField(db_index=True)
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="user_invitations")
    role = models.ForeignKey(SecurityRole, null=True, blank=True, on_delete=models.SET_NULL, related_name="user_invitations")
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="invitations")
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    is_company_admin = models.BooleanField(default=False)
    invited_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="sent_invitations")
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["empresa", "status"]),
            models.Index(fields=["email", "status"]),
        ]

    def is_valid(self):
        from django.utils import timezone
        return self.status == self.Status.PENDING and timezone.now() < self.expires_at

    def __str__(self):
        return f"{self.email} -> {self.empresa.nombre}"


class UserAuditLog(models.Model):
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="audit_events")
    target_user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="target_audit_events")
    empresa = models.ForeignKey(Empresa, null=True, blank=True, on_delete=models.SET_NULL, related_name="user_audit_events")
    action = models.CharField(max_length=120, db_index=True)
    module = models.CharField(max_length=80, default="users", db_index=True)
    detail = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["empresa", "created_at"]),
            models.Index(fields=["actor", "created_at"]),
            models.Index(fields=["target_user", "created_at"]),
        ]

    def __str__(self):
        return f"{self.action} @ {self.created_at:%Y-%m-%d %H:%M:%S}"


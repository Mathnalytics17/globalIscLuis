# models.py
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.mail import send_mail
from django.conf import settings
import uuid
    
from django.db import models
from django.contrib.auth import get_user_model

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
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(null=True, blank=True)
    
    
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



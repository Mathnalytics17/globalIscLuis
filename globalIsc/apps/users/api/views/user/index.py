from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.views import APIView
from django.conf import settings
from django.core.mail import send_mail
from apps.users.api.models.index import EmailVerificationToken, PasswordResetToken
from apps.users.api.services import audit_user_action, user_has_permission
from apps.users.api.serializers.index import (
    UserRegistrationSerializer, 
   
    UserSerializer, 
    ChangePasswordSerializer,
    EmailVerificationSerializer,
    PasswordResetRequestSerializer, 
    PasswordResetConfirmSerializer,UserDetailSerializer
)
from django.shortcuts import get_object_or_404
from permissions import IsAdmin,IsGlobal,IsLaboratorista,IsEmpresa,IsOperario,IsOwnerOrAdmin
from datetime import timedelta
import logging
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers, permissions

from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import RetrieveUpdateAPIView
from django.contrib.auth import get_user_model
from apps.users.api.serializers.index import UserSerializer
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

from rest_framework_simplejwt.exceptions import AuthenticationFailed
from django.contrib.auth import authenticate
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        # Validar que el email y contraseña estén presentes
        if not email or not password:
            raise serializers.ValidationError({
                "error": True,
                "message": "Email y contraseña son requeridos"
            })
        
        # Autenticar al usuario manualmente para tener mejor control
        user = authenticate(
            request=self.context.get('request'),
            username=email,
            password=password
        )
        
        if not user:
            raise serializers.ValidationError({
                "error": True,
                "message": "Credenciales inválidas. Verifique su email y contraseña."
            })
        
        if not user.is_active:
            raise serializers.ValidationError({
                "error": True,
                "message": "Cuenta de usuario inactiva."
            })

        if user.access_status in [User.AccessStatus.BLOCKED, User.AccessStatus.DISABLED]:
            raise serializers.ValidationError({
                "error": True,
                "message": "Cuenta bloqueada. Contacte al administrador."
            })
            
        if not user.email_verified:
            raise serializers.ValidationError({
                "error": True,
                "message": "Email no verificado. Por favor verifique su email."
            })
        
        # Si todo está bien, proceder con la generación del token
        data = super().validate(attrs)
        
        # Add custom claims
        refresh = self.get_token(self.user)
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)
        
        # Add custom user data
        data['user'] = UserSerializer(self.user).data
        
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims to token
        token['email'] = user.email
        token['role'] = user.role
        token['is_active'] = user.is_active
        token['email_verified'] = user.email_verified
        token['empresa_id'] = user.empresa_id
        token['access_status'] = user.access_status
        token['is_read_only'] = user.is_read_only
        
        return token

class LoginAV(TokenObtainPairView):
    """
    Vista personalizada para el login de usuarios
    Utiliza el serializador MyTokenObtainPairSerializer
    """
    serializer_class = MyTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
        except serializers.ValidationError as e:
            # Capturar errores de validación del serializador
            error_message = e.detail
            if isinstance(error_message, dict) and 'message' in error_message:
                message = error_message['message']
            else:
                message = "Credenciales inválidas"
                
            return Response(
                {"error": True, "message": message},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except AuthenticationFailed as e:
            return Response(
                {"error": True, "message": "Credenciales inválidas"},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            # Log the actual error for debugging
            logger.exception("Login error")
            return Response(
                {"error": True, "message": "Error interno del servidor"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
        return Response(serializer.validated_data, status=status.HTTP_200_OK)

logger = logging.getLogger(__name__)
User = get_user_model()

class UserRegistrationView(generics.CreateAPIView):
    """
    Registro público heredado. En el flujo nuevo los usuarios externos se
    activan por invitación; por seguridad queda deshabilitado por defecto.
    Puede habilitarse temporalmente con ALLOW_PUBLIC_REGISTRATION=True.
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        if not getattr(settings, "ALLOW_PUBLIC_REGISTRATION", False):
            return Response(
                {"detail": "El registro público está deshabilitado. Solicite una invitación."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().post(request, *args, **kwargs)

    def perform_create(self, serializer):
        try:
            user = serializer.save(is_active=False)  # Usuario inactivo hasta verificación
            self._send_verification_email(user)
        except Exception as e:
            logger.error(f"Error en registro de usuario: {str(e)}")
            raise

    def _send_verification_email(self, user):
        """Envía email de verificación con token"""
        try:
            # Eliminar tokens previos si existen
            EmailVerificationToken.objects.filter(user=user).delete()
            
            expires_at = timezone.now() + timedelta(days=settings.EMAIL_VERIFICATION_TOKEN_EXPIRY_DAYS)
            token = EmailVerificationToken.objects.create(
                user=user,
                expires_at=expires_at
            )
            
            verification_url = f"{settings.FRONTEND_URL}users/confirmUser?token={token.token}"
            subject = "Verifica tu correo electrónico"
            message = f"""
            Hola {user.get_full_name() or user.email},
            
            Por favor haz clic en el siguiente enlace para verificar tu correo:
            {verification_url}
            
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
        except Exception as e:
            logger.error(f"Error enviando email de verificación: {str(e)}")
            raise



class UserViewSet(viewsets.ModelViewSet):
    """
    Vista para gestión de usuarios con permisos diferenciados
    """
    queryset = User.objects.select_related("empresa").all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    def get_permissions(self):
        """
        Asigna permisos según la acción:
        - Crear/Eliminar: Solo Admin
        - Actualizar: Admin o Jefe
        - Leer: Cualquier usuario autenticado
        """
        if self.action in ['create', 'destroy']:
            permission_classes = [IsAdmin]
        elif self.action in ['update', 'partial_update']:
            permission_classes = [IsAdmin | IsGlobal]
        elif self.action in ['me', 'change_password', 'list', 'retrieve']:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.role == User.Role.GLOBAL:
            return queryset
        return queryset.filter(empresa=user.empresa)

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Endpoint para obtener datos del usuario actual"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Endpoint para cambiar contraseña"""
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        if not user.check_password(serializer.validated_data['old_password']):
            return Response(
                {"detail": "La contraseña actual es incorrecta"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        # Invalidate all tokens after password change
        user.auth_token_set.all().delete()
        
        return Response({"status": "Contraseña actualizada correctamente"})
    
    
class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.select_related("empresa").all()
    serializer_class = UserDetailSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'pk'

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if user.is_superuser or user.role == User.Role.GLOBAL:
            return queryset
        return queryset.filter(empresa=user.empresa)

    def _can_manage_users(self, permission_code="usuarios.editar"):
        user = self.request.user
        return user.is_superuser or user.role == User.Role.GLOBAL or user_has_permission(user, permission_code)

    def update(self, request, *args, **kwargs):
        target = self.get_object()
        if target != request.user and not self._can_manage_users("usuarios.editar"):
            self.permission_denied(request, message="No tiene permisos para editar este usuario.")
        response = super().update(request, *args, **kwargs)
        audit_user_action(request, "users.update", target_user=target)
        return response

    def partial_update(self, request, *args, **kwargs):
        target = self.get_object()
        if target != request.user and not self._can_manage_users("usuarios.editar"):
            self.permission_denied(request, message="No tiene permisos para editar este usuario.")
        response = super().partial_update(request, *args, **kwargs)
        audit_user_action(request, "users.partial_update", target_user=target)
        return response

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance == request.user:
            return Response({"error": "No puedes eliminarte a ti mismo"}, status=status.HTTP_403_FORBIDDEN)
        if not self._can_manage_users("usuarios.eliminar"):
            self.permission_denied(request, message="No tiene permisos para eliminar usuarios.")
        # Eliminación lógica: no borrar físicamente usuarios para conservar auditoría.
        instance.is_active = False
        instance.access_status = User.AccessStatus.DISABLED
        instance.is_read_only = True
        instance.save(update_fields=["is_active", "access_status", "is_read_only"])
        instance.company_profiles.update(status="REMOVED")
        audit_user_action(request, "users.logical_delete", target_user=instance)
        return Response({"detail": "Usuario desactivado correctamente."}, status=status.HTTP_200_OK)
class EmailVerificationView(generics.GenericAPIView):
    """
    Vista para verificación de email mediante token
    """
    serializer_class = EmailVerificationSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            token = EmailVerificationToken.objects.get(token=serializer.validated_data['token'])
            if not token.is_valid():
                return Response(
                    {"detail": "El enlace de verificación ha expirado"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            user = token.user
            if user.email_verified:
                return Response(
                    {"detail": "El email ya ha sido verificado anteriormente"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            user.email_verified = True
            #user.is_active = True
            user.save()
            token.delete()
            
            return Response({"status": "Email verificado correctamente"})
            
        except EmailVerificationToken.DoesNotExist:
            return Response(
                {"detail": "Token de verificación inválido"},
                status=status.HTTP_400_BAD_REQUEST
            )

class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        if serializer.is_valid():
            result = serializer.create(serializer.validated_data)
            return Response(result, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
import uuid
class PasswordResetConfirmView(generics.GenericAPIView):
    """
    Vista para confirmar reseteo de contraseña con token
    """
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        
        try:
            serializer.is_valid(raise_exception=True)
            token_str = serializer.validated_data['token']
            
            try:
                token_uuid = uuid.UUID(token_str)
            except ValueError:
                return Response(
                    {"detail": "Formato de token inválido"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            token = PasswordResetToken.objects.get(token=token_uuid)
            
            if not token.is_valid():
                return Response(
                    {"detail": "El enlace de recuperación ha expirado"},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            user = token.user
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            
            # Eliminar token de reset
            token.delete()
            
           
            return Response(
                {"status": "Contraseña restablecida correctamente"},
                status=status.HTTP_200_OK
            )
            
        except PasswordResetToken.DoesNotExist:
            return Response(
                {"detail": "Token de recuperación inválido"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception("Error en PasswordResetConfirmView")
            return Response(
                {"detail": "Error interno del servidor"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
User = get_user_model()

class CurrentUserView(RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
    
from rest_framework import viewsets, permissions
from django_filters.rest_framework import DjangoFilterBackend


from django.db import transaction

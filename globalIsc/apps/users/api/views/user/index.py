from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.views import APIView
from django.conf import settings
from django.core.mail import send_mail
from apps.users.api.models.index import EmailVerificationToken, PasswordResetToken
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
from rest_framework.generics import RetrieveAPIView
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

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        
        if not self.user.is_active:
            raise serializers.ValidationError("User account is not active.")
            
        if not self.user.email_verified:
            raise serializers.ValidationError("Email not verified.")
        
        # Add custom claims
        refresh = self.get_token(self.user)
        data['refresh'] = str(refresh)
        data['access'] = str(refresh.access_token)
        
        # Add custom user data
        data['user'] = {
            'email': self.user.email,
            'role': self.user.role,
            'first_name': self.user.first_name,
            'last_name': self.user.last_name,
            'is_active': self.user.is_active,
            'email_verified': self.user.email_verified
        }
        
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        
        # Add custom claims to token
        token['email'] = user.email
        token['role'] = user.role
        token['is_active'] = user.is_active
        token['email_verified'] = user.email_verified
        
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
            return Response(
                {"error": True, "message": str(e)},
                status=status.HTTP_401_UNAUTHORIZED
            )
        except Exception as e:
            return Response(
                {"error": True, "message": "Error en el servidor"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
            
        return Response(serializer.validated_data, status=status.HTTP_200_OK)



logger = logging.getLogger(__name__)
User = get_user_model()

class UserRegistrationView(generics.CreateAPIView):
    """
    Vista para registro de nuevos usuarios con verificación por email
    """
    queryset = User.objects.all()
    serializer_class = UserRegistrationSerializer
    permission_classes = [permissions.AllowAny]

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
            
            verification_url = f"{settings.FRONTEND_URL}areaPrivada/users/confirmUser?token={token.token}"
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
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]
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
        else:
            permission_classes = [permissions.AllowAny]
        return [permission() for permission in permission_classes]

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
    queryset = User.objects.all()
    serializer_class = UserDetailSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'pk'

    def perform_destroy(self, instance):
        # Lógica adicional antes de eliminar (opcional)
        if instance == self.request.user:
            return Response(
                {"error": "No puedes eliminarte a ti mismo"},
                status=status.HTTP_403_FORBIDDEN
            )
        instance.delete()
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
            user.is_active = True
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
            print(f"Error en PasswordResetConfirmView: {str(e)}")
            return Response(
                {"detail": "Error interno del servidor"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
User = get_user_model()

class CurrentUserView(RetrieveAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
    
from rest_framework import viewsets, permissions
from django_filters.rest_framework import DjangoFilterBackend


from django.db import transaction


# serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core import exceptions
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from apps.users.api.models.index  import EmailVerificationToken, PasswordResetToken
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

User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['email', 'password', 'password2', 'first_name', 'last_name', 'phone','role']
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
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role', 'phone', 'is_active', 'email_verified']
        read_only_fields = ['id', 'email', 'is_active', 'email_verified']

class UserDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'is_active', 'role', 'email_verified', 'date_joined']
        extra_kwargs = {
            'password': {'write_only': True},
            'date_joined': {'read_only': True}
        }

    def update(self, instance, validated_data):
        # Evitar que se actualice el username
        validated_data.pop('username', None)
        return super().update(instance, validated_data)
    
    
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
            reset_url = f"{settings.FRONTEND_URL}/areaPrivada/users/resetPassword?token={token.token}"
           
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
            
            print(f"Email de recuperación enviado a {user.email}: {reset_url}")  # Solo para desarrollo
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


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role', 'is_active', 'email_verified']
        read_only_fields = ['id', 'email', 'role', 'is_active', 'email_verified']
        

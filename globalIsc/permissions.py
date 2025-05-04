from rest_framework import permissions
from django.contrib.auth import get_user_model

User = get_user_model()

class BaseRolePermission(permissions.BasePermission):
    """
    Permiso base para verificar roles de usuario
    """
    role = None  # Debe ser definido en las clases hijas

    def has_permission(self, request, view):
        # Verifica que el usuario esté autenticado y tenga el rol requerido
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == self.role
        )


class IsAdmin(BaseRolePermission):
    """
    Permiso que solo permite acceso a usuarios con rol ADMIN
    """
    role = User.Role.ADMIN


class IsGlobal(BaseRolePermission):
    """
    Permiso que solo permite acceso a usuarios con rol JEFE
    """
    role = User.Role.GLOBAL


class IsLaboratorista(BaseRolePermission):
    """
    Permiso que solo permite acceso a usuarios con rol COMERCIAL
    """
    role = User.Role.LABORATORISTA

class IsEmpresa(BaseRolePermission):
    """
    Permiso que solo permite acceso a usuarios con rol COMERCIAL
    """
    role = User.Role.EMPRESA

class IsOperario(BaseRolePermission):
    """
    Permiso que solo permite acceso a usuarios con rol COMERCIAL
    """
    role = User.Role.OPERARIO

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permiso que permite acceso al dueño del recurso o a un administrador
    """
    def has_permission(self, request, view):
        # Permite el acceso si el usuario está autenticado
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Verifica si el usuario es el dueño del objeto o es administrador
        return (
            obj == request.user or 
            request.user.role == User.Role.ADMIN
        )


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Permiso que permite escritura solo al dueño, pero lectura a cualquiera
    """
    def has_permission(self, request, view):
        # Permite acceso de lectura a todos
        if request.method in permissions.SAFE_METHODS:
            return True
        # Para métodos no seguros, requiere autenticación
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Permite acceso completo al dueño, lectura a otros
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj == request.user


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permiso que permite escritura solo a administradores, pero lectura a cualquiera
    """
    def has_permission(self, request, view):
        # Permite acceso de lectura a todos
        if request.method in permissions.SAFE_METHODS:
            return True
        # Para métodos no seguros, requiere ser admin
        return (
            request.user and 
            request.user.is_authenticated and 
            request.user.role == User.Role.ADMIN
        )
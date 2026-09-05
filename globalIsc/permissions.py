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


class HasSecurityPermission(permissions.BasePermission):
    """
    Permiso basado en la matriz dinamica de roles/permisos.

    Uso en ViewSets:
        required_permission = "muestras.ver"

    Los superusuarios y usuarios GLOBAL pasan siempre. El resto se valida
    contra SecurityRole -> SecurityRolePermission -> UserCompanyProfile.
    """

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        if request.user.is_superuser or request.user.role == User.Role.GLOBAL:
            return True

        if getattr(request.user, "access_status", None) in ["BLOCKED", "DISABLED"]:
            return False

        permission_getter = getattr(view, "get_required_permission", None)
        if callable(permission_getter):
            permission_code = permission_getter()
        else:
            permission_code = getattr(view, "required_permission", None)
        if not permission_code:
            return True

        from apps.users.api.services import user_has_permission

        return user_has_permission(request.user, permission_code)


class DenyReadOnlyWrite(permissions.BasePermission):
    """
    Bloquea escrituras para usuarios o empresas en modo solo lectura.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if getattr(user, "is_read_only", False) or getattr(user, "access_status", None) == "READ_ONLY":
            return False
        empresa = getattr(user, "empresa", None)
        if empresa and getattr(empresa, "status", None) == "READ_ONLY":
            return False
        return True


class ActionPermissionMixin:
    """
    Mapea acciones de DRF a codigos de la matriz.

    Ejemplo:
        permission_action_map = {
            "list": "muestras.ver",
            "retrieve": "muestras.ver",
            "create": "muestras.crear",
        }
    """

    permission_action_map = {}
    default_read_permission = None
    default_write_permission = None

    def get_required_permission(self):
        action = getattr(self, "action", None)
        if action in self.permission_action_map:
            return self.permission_action_map[action]

        request = getattr(self, "request", None)
        if request and request.method in permissions.SAFE_METHODS:
            return self.default_read_permission
        return self.default_write_permission

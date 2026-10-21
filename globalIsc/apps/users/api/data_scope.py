"""Política única de alcance de datos por empresa.

Los permisos responden *qué* puede hacer alguien. Este módulo responde sobre
*qué empresas* puede hacerlo. Ninguna vista de negocio debe filtrar por
``user.empresa`` directamente.
"""
from apps.users.api.models.index import SecurityRole, User, UserCompanyProfile, UserDataScopeCompany


def active_role_for(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    return (
        user.company_profiles.select_related("role")
        .filter(status__in=[UserCompanyProfile.Status.ACTIVE, UserCompanyProfile.Status.READ_ONLY])
        .order_by("-is_company_admin", "id")
        .first()
    )


def effective_data_scope(user):
    if not user or not getattr(user, "is_authenticated", False):
        return SecurityRole.DataScope.ASSIGNED_COMPANIES
    if user.is_superuser or user.role == User.Role.GLOBAL:
        return SecurityRole.DataScope.ALL_COMPANIES
    if user.data_scope_override:
        return user.data_scope_override
    profile = active_role_for(user)
    return getattr(getattr(profile, "role", None), "data_scope", None) or SecurityRole.DataScope.OWN_COMPANY


def accessible_company_ids(user):
    """Return None for unrestricted access, otherwise the permitted IDs."""
    scope = effective_data_scope(user)
    if scope == SecurityRole.DataScope.ALL_COMPANIES:
        return None
    if scope in [SecurityRole.DataScope.OWN_COMPANY, SecurityRole.DataScope.GLOBAL_OIL_ONLY]:
        return {user.empresa_id} if getattr(user, "empresa_id", None) else set()
    return set(UserDataScopeCompany.objects.filter(user=user).values_list("empresa_id", flat=True))


def scope_queryset(queryset, user, company_lookup):
    """Restrict a queryset using a company field or relation lookup.

    Example: ``scope_queryset(qs, request.user, 'lote__cliente_empresa_id')``.
    """
    company_ids = accessible_company_ids(user)
    if company_ids is None:
        return queryset
    return queryset.filter(**{f"{company_lookup}__in": company_ids})


def can_access_company(user, company_id):
    if company_id is None:
        return effective_data_scope(user) == SecurityRole.DataScope.ALL_COMPANIES
    company_ids = accessible_company_ids(user)
    return company_ids is None or int(company_id) in company_ids


def is_company_audience_user(user):
    """Whether a user consumes information as a customer company.

    This is deliberately independent from the data scope.  A Global Oil
    analyst may have access to one assigned company and still needs to see its
    unpublished work. Conversely, an administrator of that company must only
    see reports explicitly released to the customer.
    """
    if not user or not getattr(user, "is_authenticated", False):
        return True
    if user.is_superuser or user.role == User.Role.GLOBAL:
        return False

    profile = active_role_for(user)
    if profile and profile.role_id:
        return profile.role.scope == SecurityRole.Scope.COMPANY

    # Compatibility for users created before SecurityRole/UserCompanyProfile.
    return user.role in [User.Role.ADMIN, User.Role.EMPRESA]


def scope_released_reports_queryset(queryset, user, company_lookup):
    """Apply tenant scope plus the customer-publication boundary to reports."""
    queryset = scope_queryset(queryset, user, company_lookup)
    if is_company_audience_user(user):
        queryset = queryset.filter(
            visible_cliente=True,
            fecha_aprobacion__isnull=False,
            usuario_aprobacion__isnull=False,
        ).exclude(estatus="anulado")
    return queryset

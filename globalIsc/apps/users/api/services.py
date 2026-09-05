import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.users.api.models.index import (
    SecurityPermission,
    SecurityRole,
    SecurityRolePermission,
    User,
    UserAuditLog,
    UserCompanyProfile,
    UserInvitation,
)


logger = logging.getLogger(__name__)


DEFAULT_PERMISSION_MATRIX = [
    ("usuarios", "ver", "usuarios.ver", "Ver usuarios"),
    ("usuarios", "invitar", "usuarios.invitar", "Invitar usuarios"),
    ("usuarios", "crear", "usuarios.crear", "Crear usuarios"),
    ("usuarios", "editar", "usuarios.editar", "Editar usuarios"),
    ("usuarios", "bloquear", "usuarios.bloquear", "Bloquear usuarios"),
    ("usuarios", "desbloquear", "usuarios.desbloquear", "Desbloquear usuarios"),
    ("usuarios", "eliminar", "usuarios.eliminar", "Eliminar usuarios"),
    ("usuarios", "reenviar_invitacion", "usuarios.reenviar_invitacion", "Reenviar invitaciones"),
    ("usuarios", "ver_auditoria", "usuarios.ver_auditoria", "Ver auditoria de usuarios"),
    ("usuarios", "asignar_roles", "usuarios.asignar_roles", "Asignar roles"),
    ("usuarios", "cambiar_empresa", "usuarios.cambiar_empresa", "Cambiar empresa de usuario"),
    ("roles", "ver", "roles.ver", "Ver roles"),
    ("roles", "crear", "roles.crear", "Crear roles"),
    ("roles", "editar", "roles.editar", "Editar roles"),
    ("roles", "eliminar", "roles.eliminar", "Eliminar roles"),
    ("roles", "asignar_permisos", "roles.asignar_permisos", "Asignar permisos a roles"),
    ("permisos", "ver_matriz", "permisos.ver_matriz", "Ver matriz de permisos"),
    ("permisos", "editar_matriz", "permisos.editar_matriz", "Editar matriz de permisos"),
    ("empresas", "ver", "empresas.ver", "Ver empresas"),
    ("empresas", "crear", "empresas.crear", "Crear empresas"),
    ("empresas", "editar", "empresas.editar", "Editar empresas"),
    ("empresas", "bloquear", "empresas.bloquear", "Bloquear empresas"),
    ("empresas", "modo_solo_lectura", "empresas.modo_solo_lectura", "Pasar empresa a solo lectura"),
    ("empresas", "eliminar", "empresas.eliminar", "Eliminar empresas"),
    ("empresas", "ver_usuarios", "empresas.ver_usuarios", "Ver usuarios de empresa"),
    ("empresas", "ver_auditoria", "empresas.ver_auditoria", "Ver auditoria de empresa"),
    ("empresas", "ver_todo_global", "empresas.ver_todo_global", "Ver informacion global"),
    ("activos", "ver", "activos.ver", "Ver arbol de activos"),
    ("activos", "crear_carpeta", "activos.crear_carpeta", "Crear carpetas"),
    ("activos", "editar_carpeta", "activos.editar_carpeta", "Editar carpetas"),
    ("activos", "eliminar_carpeta", "activos.eliminar_carpeta", "Eliminar carpetas"),
    ("activos", "sincronizar_carpetas", "activos.sincronizar_carpetas", "Sincronizar carpetas"),
    ("activos", "gestionar_puntos", "activos.gestionar_puntos", "Crear y administrar puntos de muestreo"),
    ("activos", "asignar_puntos", "activos.asignar_puntos", "Organizar muestras en puntos de muestreo"),
    ("maquinas", "ver", "maquinas.ver", "Ver maquinas"),
    ("maquinas", "crear", "maquinas.crear", "Crear maquinas"),
    ("maquinas", "editar", "maquinas.editar", "Editar maquinas"),
    ("maquinas", "eliminar", "maquinas.eliminar", "Eliminar maquinas"),
    ("lotes", "ver", "lotes.ver", "Ver lotes"),
    ("lotes", "crear", "lotes.crear", "Crear lotes"),
    ("lotes", "editar", "lotes.editar", "Editar lotes"),
    ("lotes", "eliminar", "lotes.eliminar", "Eliminar lotes"),
    ("lotes", "recalcular_estado", "lotes.recalcular_estado", "Recalcular estado de lote"),
    ("lotes", "ver_resumen", "lotes.ver_resumen", "Ver resumen de lotes"),
    ("muestras", "ver", "muestras.ver", "Ver muestras"),
    ("muestras", "crear", "muestras.crear", "Crear muestras"),
    ("muestras", "editar", "muestras.editar", "Editar muestras"),
    ("muestras", "eliminar", "muestras.eliminar", "Eliminar muestras"),
    ("muestras", "editar_atributos_tecnicos", "muestras.editar_atributos_tecnicos", "Editar atributos tecnicos"),
    ("muestras", "importar_excel", "muestras.importar_excel", "Importar muestras por Excel"),
    ("muestras", "descargar_plantilla_excel", "muestras.descargar_plantilla_excel", "Descargar plantilla Excel"),
    ("muestras", "previsualizar_excel", "muestras.previsualizar_excel", "Previsualizar Excel"),
    ("laboratorio", "ver", "laboratorio.ver", "Ver ingreso a laboratorio"),
    ("laboratorio", "ingresar_lote", "laboratorio.ingresar_lote", "Ingresar lote a laboratorio"),
    ("laboratorio", "revertir_ingreso", "laboratorio.revertir_ingreso", "Revertir ingreso a laboratorio"),
    ("laboratorio", "ver_lotes_disponibles", "laboratorio.ver_lotes_disponibles", "Ver lotes disponibles"),
    ("pruebas_muestra", "ver", "pruebas_muestra.ver", "Ver pruebas asignadas"),
    ("pruebas_muestra", "asignar", "pruebas_muestra.asignar", "Asignar pruebas"),
    ("pruebas_muestra", "editar", "pruebas_muestra.editar", "Editar pruebas asignadas"),
    ("pruebas_muestra", "eliminar", "pruebas_muestra.eliminar", "Eliminar pruebas asignadas"),
    ("pruebas_muestra", "asignar_lote", "pruebas_muestra.asignar_lote", "Asignar pruebas por lote"),
    ("pruebas_muestra", "usar_lote_predefinido", "pruebas_muestra.usar_lote_predefinido", "Usar lote predefinido"),
    ("pruebas_muestra", "definir_criterio_limite", "pruebas_muestra.definir_criterio_limite", "Definir criterio limite"),
    ("resultados", "ver", "resultados.ver", "Ver resultados"),
    ("resultados", "cargar", "resultados.cargar", "Cargar resultados"),
    ("resultados", "editar", "resultados.editar", "Editar resultados"),
    ("resultados", "eliminar", "resultados.eliminar", "Eliminar resultados"),
    ("resultados", "finalizar", "resultados.finalizar", "Finalizar resultados"),
    ("resultados", "reabrir", "resultados.reabrir", "Reabrir resultados"),
    ("resultados", "ver_historico", "resultados.ver_historico", "Ver historico de resultados"),
    ("resultados", "comentar", "resultados.comentar", "Comentar resultados"),
    ("resultados", "importar", "resultados.importar", "Importar resultados"),
    ("resultados", "exportar", "resultados.exportar", "Exportar resultados"),
    ("revision", "ver", "revision.ver", "Ver revision"),
    ("revision", "aprobar_resultados", "revision.aprobar_resultados", "Aprobar resultados"),
    ("revision", "rechazar_resultados", "revision.rechazar_resultados", "Rechazar resultados"),
    ("revision", "editar_estado", "revision.editar_estado", "Editar estado de revision"),
    ("revision", "ver_historico", "revision.ver_historico", "Ver historico de revision"),
    ("interpretacion", "ver", "interpretacion.ver", "Ver interpretacion"),
    ("interpretacion", "editar", "interpretacion.editar", "Editar interpretacion"),
    ("interpretacion", "guardar", "interpretacion.guardar", "Guardar interpretacion"),
    ("interpretacion", "finalizar", "interpretacion.finalizar", "Finalizar interpretacion"),
    ("interpretacion", "reabrir", "interpretacion.reabrir", "Reabrir interpretacion"),
    ("interpretacion", "editar_comentarios", "interpretacion.editar_comentarios", "Editar comentarios"),
    ("interpretacion", "editar_conclusion", "interpretacion.editar_conclusion", "Editar conclusion"),
    ("interpretacion", "ver_tendencias", "interpretacion.ver_tendencias", "Ver tendencias"),
    ("reportes", "ver", "reportes.ver", "Ver reportes"),
    ("reportes", "generar", "reportes.generar", "Generar reportes"),
    ("reportes", "previsualizar", "reportes.previsualizar", "Previsualizar reportes"),
    ("reportes", "descargar_pdf", "reportes.descargar_pdf", "Descargar PDF"),
    ("reportes", "publicar_cliente", "reportes.publicar_cliente", "Publicar a cliente"),
    ("reportes", "despublicar_cliente", "reportes.despublicar_cliente", "Despublicar a cliente"),
    ("reportes", "enviar_email", "reportes.enviar_email", "Enviar reporte por email"),
    ("reportes", "ver_versiones", "reportes.ver_versiones", "Ver versiones"),
    ("reportes", "restaurar_version", "reportes.restaurar_version", "Restaurar version"),
    ("reportes", "subir_firma", "reportes.subir_firma", "Subir firma"),
    ("reportes", "ver_dashboard", "reportes.ver_dashboard", "Ver dashboard de reportes"),
    ("config_tecnica", "ver", "config_tecnica.ver", "Ver configuracion tecnica"),
    ("config_tecnica", "editar", "config_tecnica.editar", "Editar configuracion tecnica"),
    ("catalogos_tecnicos", "ver", "catalogos_tecnicos.ver", "Ver catalogos tecnicos"),
    ("catalogos_tecnicos", "crear", "catalogos_tecnicos.crear", "Crear catalogos tecnicos"),
    ("catalogos_tecnicos", "editar", "catalogos_tecnicos.editar", "Editar catalogos tecnicos"),
    ("catalogos_tecnicos", "eliminar", "catalogos_tecnicos.eliminar", "Eliminar catalogos tecnicos"),
    ("catalogos_tecnicos", "restaurar", "catalogos_tecnicos.restaurar", "Restaurar catalogos tecnicos"),
    ("valores_limite", "ver", "valores_limite.ver", "Ver valores limite"),
    ("valores_limite", "editar_matriz", "valores_limite.editar_matriz", "Editar matriz de limites"),
    ("pruebas", "ver", "pruebas.ver", "Ver pruebas"),
    ("pruebas", "crear", "pruebas.crear", "Crear pruebas"),
    ("pruebas", "editar", "pruebas.editar", "Editar pruebas"),
    ("pruebas", "eliminar", "pruebas.eliminar", "Eliminar pruebas"),
    ("pruebas", "restaurar", "pruebas.restaurar", "Restaurar pruebas"),
    ("unidades", "ver", "unidades.ver", "Ver unidades"),
    ("unidades", "crear", "unidades.crear", "Crear unidades"),
    ("unidades", "editar", "unidades.editar", "Editar unidades"),
    ("unidades", "eliminar", "unidades.eliminar", "Eliminar unidades"),
    ("condiciones", "ver", "condiciones.ver", "Ver condiciones"),
    ("condiciones", "crear", "condiciones.crear", "Crear condiciones"),
    ("condiciones", "editar", "condiciones.editar", "Editar condiciones"),
    ("condiciones", "eliminar", "condiciones.eliminar", "Eliminar condiciones"),
    ("equipos_prueba", "ver", "equipos_prueba.ver", "Ver equipos de prueba"),
    ("equipos_prueba", "crear", "equipos_prueba.crear", "Crear equipos de prueba"),
    ("equipos_prueba", "editar", "equipos_prueba.editar", "Editar equipos de prueba"),
    ("equipos_prueba", "eliminar", "equipos_prueba.eliminar", "Eliminar equipos de prueba"),
    ("lotes_predefinidos", "ver", "lotes_predefinidos.ver", "Ver lotes predefinidos"),
    ("lotes_predefinidos", "crear", "lotes_predefinidos.crear", "Crear lotes predefinidos"),
    ("lotes_predefinidos", "editar", "lotes_predefinidos.editar", "Editar lotes predefinidos"),
    ("lotes_predefinidos", "eliminar", "lotes_predefinidos.eliminar", "Eliminar lotes predefinidos"),
    ("tipos_gestion", "ver", "tipos_gestion.ver", "Ver tipos de gestion"),
    ("tipos_gestion", "crear", "tipos_gestion.crear", "Crear tipos de gestion"),
    ("tipos_gestion", "editar", "tipos_gestion.editar", "Editar tipos de gestion"),
    ("tipos_gestion", "eliminar", "tipos_gestion.eliminar", "Eliminar tipos de gestion"),
    ("campos_extra", "ver", "campos_extra.ver", "Ver campos extra"),
    ("campos_extra", "crear", "campos_extra.crear", "Crear campos extra"),
    ("campos_extra", "editar", "campos_extra.editar", "Editar campos extra"),
    ("campos_extra", "eliminar", "campos_extra.eliminar", "Eliminar campos extra"),
    ("campos_extra", "clonar", "campos_extra.clonar", "Clonar campos extra"),
    ("campos_extra", "cambiar_estado", "campos_extra.cambiar_estado", "Cambiar estado de campos extra"),
    ("dashboard", "ver_global", "dashboard.ver_global", "Ver dashboard global"),
    ("dashboard", "ver_empresa", "dashboard.ver_empresa", "Ver dashboard de empresa"),
    ("dashboard", "ver_laboratorio", "dashboard.ver_laboratorio", "Ver dashboard de laboratorio"),
    ("dashboard", "ver_reportes", "dashboard.ver_reportes", "Ver dashboard de reportes"),
]

ROLE_DEFINITIONS = [
    ("Administrador Global", "admin_global", SecurityRole.Scope.GLOBAL, User.Role.GLOBAL),
    ("Administrador de Empresa", "admin_empresa", SecurityRole.Scope.COMPANY, User.Role.ADMIN),
    ("Usuario Empresa Consulta", "empresa_consulta", SecurityRole.Scope.COMPANY, User.Role.EMPRESA),
    ("Usuario Empresa Carga Muestras", "empresa_carga_muestras", SecurityRole.Scope.COMPANY, User.Role.EMPRESA),
    ("Laboratorista", "laboratorista", SecurityRole.Scope.INTERNAL, User.Role.LABORATORISTA),
    ("Revisor Interpretador", "revisor_interpretador", SecurityRole.Scope.INTERNAL, User.Role.LABORATORISTA),
    ("Solo Lectura", "solo_lectura", SecurityRole.Scope.COMPANY, User.Role.EMPRESA),
]


READONLY_PREFIXES = [
    "activos.ver",
    "maquinas.ver",
    "lotes.ver",
    "lotes.ver_resumen",
    "muestras.ver",
    "reportes.ver",
    "reportes.descargar_pdf",
    "reportes.ver_versiones",
    "reportes.ver_dashboard",
    "dashboard.ver_empresa",
]

COMPANY_ADMIN_CODES = [
    "usuarios.ver",
    "usuarios.invitar",
    "usuarios.editar",
    "usuarios.bloquear",
    "usuarios.desbloquear",
    "usuarios.reenviar_invitacion",
    "usuarios.ver_auditoria",
    "usuarios.asignar_roles",
    "empresas.ver",
    "empresas.editar",
    "empresas.ver_usuarios",
    "empresas.ver_auditoria",
    "activos.ver",
    "activos.crear_carpeta",
    "activos.editar_carpeta",
    "activos.eliminar_carpeta",
    "activos.sincronizar_carpetas",
    "activos.gestionar_puntos",
    "activos.asignar_puntos",
    "maquinas.ver",
    "maquinas.crear",
    "maquinas.editar",
    "maquinas.eliminar",
    "lotes.ver",
    "lotes.crear",
    "lotes.editar",
    "lotes.eliminar",
    "lotes.recalcular_estado",
    "lotes.ver_resumen",
    "muestras.ver",
    "muestras.crear",
    "muestras.editar",
    "muestras.eliminar",
    "muestras.editar_atributos_tecnicos",
    "muestras.importar_excel",
    "muestras.descargar_plantilla_excel",
    "muestras.previsualizar_excel",
    "catalogos_tecnicos.ver",
    "tipos_gestion.ver",
    "empresas.ver",
    "reportes.ver",
    "reportes.descargar_pdf",
    "reportes.ver_versiones",
    "reportes.ver_dashboard",
    "dashboard.ver_empresa",
]

COMPANY_SAMPLE_LOADER_CODES = [
    "activos.ver",
    "activos.asignar_puntos",
    "maquinas.ver",
    "maquinas.crear",
    "maquinas.editar",
    "lotes.ver",
    "lotes.crear",
    "lotes.editar",
    "lotes.ver_resumen",
    "muestras.ver",
    "muestras.crear",
    "muestras.editar",
    "muestras.editar_atributos_tecnicos",
    "muestras.importar_excel",
    "muestras.descargar_plantilla_excel",
    "muestras.previsualizar_excel",
    "catalogos_tecnicos.ver",
    "tipos_gestion.ver",
    "empresas.ver",
    "reportes.ver",
    "reportes.descargar_pdf",
    "reportes.ver_dashboard",
    "dashboard.ver_empresa",
]

LAB_CODES = [
    "laboratorio.ver",
    "laboratorio.ingresar_lote",
    "laboratorio.revertir_ingreso",
    "laboratorio.ver_lotes_disponibles",
    "pruebas_muestra.ver",
    "pruebas_muestra.asignar",
    "pruebas_muestra.editar",
    "pruebas_muestra.eliminar",
    "pruebas_muestra.asignar_lote",
    "pruebas_muestra.usar_lote_predefinido",
    "pruebas_muestra.definir_criterio_limite",
    "resultados.ver",
    "resultados.cargar",
    "resultados.editar",
    "resultados.eliminar",
    "resultados.finalizar",
    "resultados.reabrir",
    "resultados.ver_historico",
    "resultados.comentar",
    "resultados.importar",
    "resultados.exportar",
    "revision.ver",
    "dashboard.ver_laboratorio",
]

REVIEWER_CODES = [
    "revision.ver",
    "revision.aprobar_resultados",
    "revision.rechazar_resultados",
    "revision.editar_estado",
    "revision.ver_historico",
    "interpretacion.ver",
    "interpretacion.editar",
    "interpretacion.guardar",
    "interpretacion.finalizar",
    "interpretacion.reabrir",
    "interpretacion.editar_comentarios",
    "interpretacion.editar_conclusion",
    "interpretacion.ver_tendencias",
    "reportes.ver",
    "reportes.generar",
    "reportes.previsualizar",
    "reportes.descargar_pdf",
    "reportes.publicar_cliente",
    "reportes.despublicar_cliente",
    "reportes.enviar_email",
    "reportes.ver_versiones",
    "reportes.restaurar_version",
    "reportes.subir_firma",
    "reportes.ver_dashboard",
    "resultados.ver",
    "resultados.ver_historico",
    "dashboard.ver_reportes",
]


def seed_default_permissions():
    for module, action, code, description in DEFAULT_PERMISSION_MATRIX:
        SecurityPermission.objects.update_or_create(
            code=code,
            defaults={
                "module": module,
                "action": action,
                "description": description,
                "active": True,
            },
        )
    sync_default_roles_and_permissions()


def sync_default_roles_and_permissions():
    roles = {}
    for name, code, scope, legacy_role in ROLE_DEFINITIONS:
        role, _ = SecurityRole.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "scope": scope,
                "legacy_role": legacy_role,
                "editable": code != "admin_global",
                "active": True,
            },
        )
        roles[code] = role

    all_codes = set(SecurityPermission.objects.filter(active=True).values_list("code", flat=True))
    grants = {
        "admin_global": all_codes,
        "admin_empresa": set(COMPANY_ADMIN_CODES),
        "empresa_consulta": {code for code in all_codes if code in READONLY_PREFIXES},
        "solo_lectura": {code for code in all_codes if code in READONLY_PREFIXES},
        "empresa_carga_muestras": set(COMPANY_SAMPLE_LOADER_CODES),
        "laboratorista": set(LAB_CODES),
        "revisor_interpretador": set(REVIEWER_CODES),
    }

    permission_by_code = {
        permission.code: permission
        for permission in SecurityPermission.objects.filter(code__in=set().union(*grants.values()))
    }

    for role_code, permission_codes in grants.items():
        role = roles.get(role_code)
        if not role:
            continue
        SecurityRolePermission.objects.filter(role=role).update(allowed=False)
        for permission_code in permission_codes:
            permission = permission_by_code.get(permission_code)
            if permission:
                SecurityRolePermission.objects.update_or_create(
                    role=role,
                    permission=permission,
                    defaults={"allowed": True},
                )


def audit_user_action(request, action, target_user=None, empresa=None, detail="", metadata=None):
    actor = getattr(request, "user", None)
    if not actor or not actor.is_authenticated:
        actor = None
    return UserAuditLog.objects.create(
        actor=actor,
        target_user=target_user,
        empresa=empresa or getattr(target_user, "empresa", None),
        action=action,
        detail=detail,
        metadata=metadata or {},
        ip_address=_client_ip(request),
        user_agent=(request.META.get("HTTP_USER_AGENT", "") if request else ""),
    )


def _client_ip(request):
    if not request:
        return None
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def default_company_role():
    return SecurityRole.objects.filter(code="empresa_consulta", active=True).first()

def is_global_user(user):
    return bool(user and getattr(user, "is_authenticated", False) and (getattr(user, "is_superuser", False) or getattr(user, "role", None) == User.Role.GLOBAL))

def is_role_assignable_by(actor, role):
    if role is None:
        return True
    if is_global_user(actor):
        return True
    return role.scope == SecurityRole.Scope.COMPANY and role.active


def user_has_permission(user, permission_code, empresa=None):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or user.role == User.Role.GLOBAL:
        return True
    if user.access_status in [User.AccessStatus.BLOCKED, User.AccessStatus.DISABLED]:
        return False
    profiles = user.company_profiles.filter(status__in=[
        UserCompanyProfile.Status.ACTIVE,
        UserCompanyProfile.Status.READ_ONLY,
    ])
    if empresa is not None:
        profiles = profiles.filter(empresa=empresa)
    return SecurityPermission.objects.filter(
        code=permission_code,
        active=True,
        permission_roles__allowed=True,
        permission_roles__role__user_profiles__in=profiles,
    ).exists()


def ensure_user_profile(user, empresa, role=None, is_company_admin=False, status=None):
    profile, _ = UserCompanyProfile.objects.update_or_create(
        user=user,
        empresa=empresa,
        defaults={
            "role": role,
            "is_company_admin": is_company_admin,
            "status": status or UserCompanyProfile.Status.ACTIVE,
            "activated_at": timezone.now() if (status or UserCompanyProfile.Status.ACTIVE) == UserCompanyProfile.Status.ACTIVE else None,
        },
    )
    return profile


@transaction.atomic
def create_invitation(email, empresa, invited_by=None, role=None, is_company_admin=False, metadata=None):
    normalized_email = User.objects.normalize_email(email)
    if role is None:
        role = default_company_role()
    if role is not None and role.scope != SecurityRole.Scope.COMPANY:
        raise ValueError("Solo se pueden invitar usuarios externos con roles de empresa.")
    UserInvitation.objects.filter(
        email__iexact=normalized_email,
        empresa=empresa,
        status=UserInvitation.Status.PENDING,
    ).update(status=UserInvitation.Status.REVOKED, revoked_at=timezone.now())

    user, created = User.objects.get_or_create(
        email=normalized_email,
        defaults={
            "empresa": empresa,
            "role": User.Role.EMPRESA,
            "is_active": False,
            "email_verified": False,
            "access_status": User.AccessStatus.PENDING_INVITATION,
        },
    )
    if not created and user.empresa_id != empresa.id:
        raise ValueError("El correo ya pertenece a otra empresa.")

    invitation = UserInvitation.objects.create(
        email=normalized_email,
        empresa=empresa,
        role=role,
        user=user,
        invited_by=invited_by if getattr(invited_by, "is_authenticated", False) else None,
        is_company_admin=is_company_admin,
        expires_at=timezone.now() + timedelta(days=getattr(settings, "EMAIL_VERIFICATION_TOKEN_EXPIRY_DAYS", 3)),
        metadata=metadata or {},
    )
    ensure_user_profile(
        user,
        empresa,
        role=role,
        is_company_admin=is_company_admin,
        status=UserCompanyProfile.Status.PENDING,
    )
    invitation.email_sent, invitation.email_error = deliver_invitation_email(invitation)
    return invitation


def deliver_invitation_email(invitation):
    """Send an invitation without turning a transient SMTP failure into an HTTP 500."""
    try:
        sent = send_invitation_email(invitation)
        if sent < 1:
            raise RuntimeError("El servidor de correo no aceptó el mensaje.")
    except Exception as exc:  # SMTP backends raise several unrelated exception types.
        logger.exception(
            "No se pudo enviar la invitacion %s a %s",
            invitation.pk,
            invitation.email,
        )
        delivery = {
            "status": "failed",
            "attempted_at": timezone.now().isoformat(),
            "error_type": type(exc).__name__,
        }
        invitation.metadata = {**(invitation.metadata or {}), "email_delivery": delivery}
        invitation.save(update_fields=["metadata", "updated_at"])
        return False, "No se pudo enviar el correo. La invitación quedó pendiente para reenvío."

    delivery = {
        "status": "sent",
        "attempted_at": timezone.now().isoformat(),
    }
    invitation.metadata = {**(invitation.metadata or {}), "email_delivery": delivery}
    invitation.save(update_fields=["metadata", "updated_at"])
    return True, ""


def send_invitation_email(invitation):
    invite_url = f"{settings.FRONTEND_URL}users/confirmUser?token={invitation.token}&invite=1"
    subject = "Invitacion a Global Oil"
    message = (
        f"Hola,\n\n"
        f"Has sido invitado a Global Oil para la empresa {invitation.empresa.nombre}.\n"
        f"Completa tu cuenta en el siguiente enlace:\n{invite_url}\n\n"
        f"Este enlace expira el {invitation.expires_at:%d/%m/%Y %H:%M}.\n"
    )
    return send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [invitation.email], fail_silently=False)


@transaction.atomic
def accept_invitation(token, first_name, last_name, password, phone="", avatar=None):
    invitation = (
        UserInvitation.objects
        .select_for_update(of=("self",))
        .select_related("user", "empresa", "role")
        .get(token=token)
    )
    if not invitation.is_valid():
        raise ValueError("La invitacion no es valida o ya expiro.")

    user = invitation.user
    if user is None:
        user = User.objects.create_user(
            email=invitation.email,
            empresa=invitation.empresa,
            role=User.Role.EMPRESA,
        )
        invitation.user = user

    user.first_name = first_name
    user.last_name = last_name
    user.phone = phone or user.phone
    if avatar is not None:
        user.avatar = avatar
    user.empresa = invitation.empresa
    user.email_verified = True
    user.is_active = True
    user.access_status = User.AccessStatus.ACTIVE
    user.set_password(password)
    user.save()

    ensure_user_profile(
        user,
        invitation.empresa,
        role=invitation.role,
        is_company_admin=invitation.is_company_admin,
        status=UserCompanyProfile.Status.ACTIVE,
    )
    invitation.status = UserInvitation.Status.ACCEPTED
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["status", "accepted_at", "user", "updated_at"])
    send_welcome_email(user)
    return user


def send_welcome_email(user):
    subject = "Cuenta Global Oil activada"
    message = (
        f"Hola {user.get_full_name() or user.email},\n\n"
        f"Tu cuenta de Global Oil fue activada correctamente.\n"
        f"Puedes ingresar desde {settings.FRONTEND_URL}users/login\n"
    )
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)


def generate_temp_password():
    return secrets.token_urlsafe(16)

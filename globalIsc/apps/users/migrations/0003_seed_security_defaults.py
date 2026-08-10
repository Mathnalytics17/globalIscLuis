from django.db import migrations
from django.utils import timezone


PERMISSIONS = [
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
    ("Administrador Global", "admin_global", "GLOBAL", "GLOBAL"),
    ("Administrador de Empresa", "admin_empresa", "COMPANY", "ADMINISTRADOR"),
    ("Usuario Empresa Consulta", "empresa_consulta", "COMPANY", "EMPRESA"),
    ("Usuario Empresa Carga Muestras", "empresa_carga_muestras", "COMPANY", "EMPRESA"),
    ("Laboratorista", "laboratorista", "INTERNAL", "LABORATORISTA"),
    ("Revisor Interpretador", "revisor_interpretador", "INTERNAL", "LABORATORISTA"),
    ("Solo Lectura", "solo_lectura", "COMPANY", "EMPRESA"),
]


def seed_security(apps, schema_editor):
    Permission = apps.get_model("users", "SecurityPermission")
    Role = apps.get_model("users", "SecurityRole")
    RolePermission = apps.get_model("users", "SecurityRolePermission")
    User = apps.get_model("users", "User")
    Profile = apps.get_model("users", "UserCompanyProfile")

    for module, action, code, description in PERMISSIONS:
        Permission.objects.update_or_create(
            code=code,
            defaults={"module": module, "action": action, "description": description, "active": True},
        )

    roles = {}
    for name, code, scope, legacy_role in ROLE_DEFINITIONS:
        role, _ = Role.objects.update_or_create(
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

    all_permissions = list(Permission.objects.filter(active=True))
    readonly_codes = [code for _, _, code, _ in PERMISSIONS if code.endswith(".ver") or code.startswith("dashboard.")]
    sample_loader_prefixes = [
        "lotes.",
        "muestras.",
        "activos.",
        "maquinas.",
        "catalogos_tecnicos.ver",
        "tipos_gestion.ver",
        "empresas.ver",
        "reportes.ver",
        "reportes.descargar_pdf",
        "dashboard.",
    ]
    lab_prefixes = ["laboratorio.", "pruebas_muestra.", "resultados.", "revision.ver", "dashboard.ver_laboratorio"]
    reviewer_prefixes = ["revision.", "interpretacion.", "reportes.", "resultados.ver", "resultados.ver_historico", "dashboard."]

    grants = {
        "admin_global": [p.code for p in all_permissions],
        "admin_empresa": [p.code for p in all_permissions if not p.code.startswith(("empresas.crear", "empresas.eliminar", "roles.", "permisos.", "config_tecnica.editar"))],
        "empresa_consulta": readonly_codes,
        "empresa_carga_muestras": [p.code for p in all_permissions if any(p.code.startswith(prefix) for prefix in sample_loader_prefixes)],
        "laboratorista": [p.code for p in all_permissions if any(p.code.startswith(prefix) for prefix in lab_prefixes)],
        "revisor_interpretador": [p.code for p in all_permissions if any(p.code.startswith(prefix) for prefix in reviewer_prefixes)],
        "solo_lectura": readonly_codes,
    }

    permission_by_code = {p.code: p for p in all_permissions}
    for role_code, permission_codes in grants.items():
        role = roles[role_code]
        for permission_code in permission_codes:
            permission = permission_by_code.get(permission_code)
            if permission:
                RolePermission.objects.update_or_create(role=role, permission=permission, defaults={"allowed": True})

    role_by_legacy = {
        "GLOBAL": roles["admin_global"],
        "ADMINISTRADOR": roles["admin_empresa"],
        "EMPRESA": roles["empresa_carga_muestras"],
        "LABORATORISTA": roles["laboratorista"],
        "OPERARIO": roles["empresa_carga_muestras"],
    }
    now = timezone.now()
    for user in User.objects.select_related("empresa").all():
        access_status = "ACTIVE" if user.is_active else "PENDING_INVITATION"
        User.objects.filter(pk=user.pk).update(access_status=access_status)
        Profile.objects.update_or_create(
            user=user,
            empresa=user.empresa,
            defaults={
                "role": role_by_legacy.get(user.role),
                "is_company_admin": user.role in ["GLOBAL", "ADMINISTRADOR"],
                "status": "ACTIVE" if user.is_active else "PENDING",
                "activated_at": now if user.is_active else None,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0002_user_access_status_user_block_reason_user_blocked_at_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_security, migrations.RunPython.noop),
    ]

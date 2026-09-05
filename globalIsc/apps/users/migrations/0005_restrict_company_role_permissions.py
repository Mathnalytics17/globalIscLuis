from django.db import migrations


ROLE_GRANTS = {
    "admin_empresa": [
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
        "reportes.ver",
        "reportes.descargar_pdf",
        "reportes.ver_versiones",
        "reportes.ver_dashboard",
        "dashboard.ver_empresa",
    ],
    "empresa_carga_muestras": [
        "activos.ver",
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
    ],
    "empresa_consulta": [
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
    ],
    "solo_lectura": [
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
    ],
}


def restrict_company_role_permissions(apps, schema_editor):
    Role = apps.get_model("users", "SecurityRole")
    Permission = apps.get_model("users", "SecurityPermission")
    RolePermission = apps.get_model("users", "SecurityRolePermission")

    permissions = {
        permission.code: permission
        for permission in Permission.objects.filter(code__in={code for codes in ROLE_GRANTS.values() for code in codes})
    }

    for role_code, permission_codes in ROLE_GRANTS.items():
        role = Role.objects.filter(code=role_code).first()
        if not role:
            continue

        RolePermission.objects.filter(role=role).update(allowed=False)
        for permission_code in permission_codes:
            permission = permissions.get(permission_code)
            if permission:
                RolePermission.objects.update_or_create(
                    role=role,
                    permission=permission,
                    defaults={"allowed": True},
                )


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0004_harden_security_user_fields"),
    ]

    operations = [
        migrations.RunPython(restrict_company_role_permissions, migrations.RunPython.noop),
    ]

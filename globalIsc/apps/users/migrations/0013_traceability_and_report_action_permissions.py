from django.db import migrations


PERMISSIONS = [
    ("reportes", "aprobar", "reportes.aprobar", "Aprobar reportes"),
    ("reportes", "anular", "reportes.anular", "Anular reportes"),
    ("trazabilidad", "ver", "trazabilidad.ver", "Consultar trazabilidad operacional"),
    ("importaciones", "ver", "importaciones.ver", "Consultar corridas de importación"),
]


def add_permissions(apps, schema_editor):
    Permission = apps.get_model("users", "SecurityPermission")
    Role = apps.get_model("users", "SecurityRole")
    RolePermission = apps.get_model("users", "SecurityRolePermission")

    permissions = {}
    for module, action, code, description in PERMISSIONS:
        permission, _ = Permission.objects.update_or_create(
            code=code,
            defaults={
                "module": module,
                "action": action,
                "description": description,
                "active": True,
            },
        )
        permissions[code] = permission

    # GlobalOil is always allowed. Company administrators get the two
    # supervisory views by default; sample loaders intentionally do not.
    grants = {
        "admin_global": list(permissions),
        "admin_empresa": ["trazabilidad.ver", "importaciones.ver"],
        "revisor_interpretador": ["reportes.aprobar", "reportes.anular"],
    }
    for role_code, codes in grants.items():
        for role in Role.objects.filter(code=role_code):
            for code in codes:
                RolePermission.objects.update_or_create(
                    role=role,
                    permission=permissions[code],
                    defaults={"allowed": True},
                )


class Migration(migrations.Migration):
    dependencies = [("users", "0012_limit_version_permissions")]

    operations = [migrations.RunPython(add_permissions, migrations.RunPython.noop)]

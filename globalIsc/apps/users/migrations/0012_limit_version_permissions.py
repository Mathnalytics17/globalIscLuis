from django.db import migrations


PERMISSIONS = [
    ("valores_limite", "crear_version", "valores_limite.crear_version", "Crear una nueva versión de límites"),
    ("valores_limite", "importar_matriz", "valores_limite.importar_matriz", "Importar matriz de límites"),
    ("valores_limite", "activar_version", "valores_limite.activar_version", "Activar una versión de límites"),
    ("valores_limite", "desactivar_version", "valores_limite.desactivar_version", "Desactivar una versión de límites"),
]


def add_limit_version_permissions(apps, schema_editor):
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

    for role in Role.objects.filter(code="admin_global"):
        for permission in permissions.values():
            RolePermission.objects.update_or_create(
                role=role,
                permission=permission,
                defaults={"allowed": True},
            )


class Migration(migrations.Migration):
    dependencies = [("users", "0011_user_session_epoch")]

    operations = [
        migrations.RunPython(add_limit_version_permissions, migrations.RunPython.noop),
    ]

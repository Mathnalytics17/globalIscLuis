from django.db import migrations


PERMISSIONS = [
    ('gestionar_puntos', 'activos.gestionar_puntos', 'Crear y administrar puntos de muestreo'),
    ('asignar_puntos', 'activos.asignar_puntos', 'Organizar muestras en puntos de muestreo'),
]


def add_permissions(apps, schema_editor):
    Permission = apps.get_model('users', 'SecurityPermission')
    Role = apps.get_model('users', 'SecurityRole')
    RolePermission = apps.get_model('users', 'SecurityRolePermission')
    created = {}
    for action, code, description in PERMISSIONS:
        permission, _ = Permission.objects.get_or_create(
            code=code,
            defaults={'module': 'activos', 'action': action, 'description': description},
        )
        created[code] = permission
    for role in Role.objects.filter(code='admin_empresa'):
        for permission in created.values():
            RolePermission.objects.get_or_create(role=role, permission=permission)
    for role in Role.objects.filter(code='empresa_carga_muestras'):
        RolePermission.objects.get_or_create(role=role, permission=created['activos.asignar_puntos'])


class Migration(migrations.Migration):
    dependencies = [('users', '0006_user_firma_predeterminada')]
    operations = [migrations.RunPython(add_permissions, migrations.RunPython.noop)]

from django.db import migrations


LEGACY_DASHBOARD_CODES = [
    "dashboard.ver_empresa",
    "dashboard.ver_laboratorio",
    "dashboard.ver_reportes",
]


def disable_legacy_dashboard_permissions(apps, schema_editor):
    Permission = apps.get_model("users", "SecurityPermission")
    Permission.objects.filter(code__in=LEGACY_DASHBOARD_CODES).update(active=False)


class Migration(migrations.Migration):
    dependencies = [("users", "0014_user_home_path")]

    operations = [migrations.RunPython(disable_legacy_dashboard_permissions, migrations.RunPython.noop)]

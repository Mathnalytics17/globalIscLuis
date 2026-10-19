from django.db import migrations, models


DEFAULT_ROLE_HOME_PATHS = {
    "admin_global": "/dashboard",
    "admin_empresa": "/muestras/lotes",
    "empresa_consulta": "/reportes",
    "solo_lectura": "/reportes",
    "empresa_carga_muestras": "/muestras/nuevo-lote",
    "laboratorista": "/muestras/laboratorio",
    "revisor_interpretador": "/muestras/revision-resultados",
}


def assign_default_role_homes(apps, schema_editor):
    Role = apps.get_model("users", "SecurityRole")
    for code, path in DEFAULT_ROLE_HOME_PATHS.items():
        Role.objects.filter(code=code).update(default_home_path=path)


class Migration(migrations.Migration):
    dependencies = [("users", "0015_dashboard_global_only")]

    operations = [
        migrations.AddField(
            model_name="securityrole",
            name="default_home_path",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
        migrations.RunPython(assign_default_role_homes, migrations.RunPython.noop),
    ]

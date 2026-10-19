from django.db import migrations, models
import django.db.models.deletion


ROLE_SCOPES = {
    "admin_global": "ALL_COMPANIES",
    "admin_empresa": "OWN_COMPANY",
    "empresa_consulta": "OWN_COMPANY",
    "solo_lectura": "OWN_COMPANY",
    "empresa_carga_muestras": "OWN_COMPANY",
    "laboratorista": "ALL_COMPANIES",
    "revisor_interpretador": "ALL_COMPANIES",
}


def seed_role_scopes(apps, schema_editor):
    Role = apps.get_model("users", "SecurityRole")
    for code, scope in ROLE_SCOPES.items():
        Role.objects.filter(code=code).update(data_scope=scope)


class Migration(migrations.Migration):
    dependencies = [("users", "0016_security_role_default_home_path")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="data_scope_override",
            field=models.CharField(blank=True, choices=[("", "Heredar del rol"), ("OWN_COMPANY", "Solo su empresa"), ("ALL_COMPANIES", "Todas las empresas"), ("ASSIGNED_COMPANIES", "Empresas asignadas"), ("GLOBAL_OIL_ONLY", "Solo Global Oil")], default="", max_length=32),
        ),
        migrations.AddField(
            model_name="securityrole",
            name="data_scope",
            field=models.CharField(choices=[("OWN_COMPANY", "Solo su empresa"), ("ALL_COMPANIES", "Todas las empresas"), ("ASSIGNED_COMPANIES", "Empresas asignadas"), ("GLOBAL_OIL_ONLY", "Solo Global Oil")], db_index=True, default="OWN_COMPANY", max_length=32),
        ),
        migrations.CreateModel(
            name="UserDataScopeCompany",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("assigned_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_data_scopes", to="users.user")),
                ("empresa", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="data_scope_users", to="misc.empresa")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="data_scope_companies", to="users.user")),
            ],
            options={"unique_together": {("user", "empresa")}},
        ),
        migrations.AddIndex(model_name="userdatascopecompany", index=models.Index(fields=["user", "empresa"], name="users_userd_user_id_fd6b40_idx")),
        migrations.RunPython(seed_role_scopes, migrations.RunPython.noop),
    ]

from django.db import migrations


LABORATORIST_REPORT_CODES = (
    "reportes.ver",
    "reportes.generar",
    "reportes.previsualizar",
    "reportes.descargar_pdf",
    "reportes.subir_firma",
    "reportes.ver_versiones",
    "reportes.ver_dashboard",
)


def grant_report_workflow(apps, schema_editor):
    Role = apps.get_model("users", "SecurityRole")
    Permission = apps.get_model("users", "SecurityPermission")
    RolePermission = apps.get_model("users", "SecurityRolePermission")

    role = Role.objects.filter(code="laboratorista").first()
    if not role:
        return

    permissions = Permission.objects.filter(code__in=LABORATORIST_REPORT_CODES, active=True)
    for permission in permissions:
        RolePermission.objects.update_or_create(
            role=role,
            permission=permission,
            defaults={"allowed": True},
        )


class Migration(migrations.Migration):
    dependencies = [("users", "0017_role_data_scope_and_assignments")]

    operations = [migrations.RunPython(grant_report_workflow, migrations.RunPython.noop)]

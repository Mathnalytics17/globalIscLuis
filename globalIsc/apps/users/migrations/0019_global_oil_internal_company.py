from django.db import migrations


def establish_global_oil_company(apps, schema_editor):
    Empresa = apps.get_model("misc", "Empresa")
    User = apps.get_model("users", "User")
    SecurityRole = apps.get_model("users", "SecurityRole")
    UserCompanyProfile = apps.get_model("users", "UserCompanyProfile")

    company, _ = Empresa.objects.get_or_create(
        nit="GLOBAL-OIL-INTERNAL",
        defaults={
            "nombre": "Global Oil",
            "email": "contacto@globaloil.local",
            "is_active": True,
            "is_internal": True,
            "status": "ACTIVE",
        },
    )
    if not company.is_internal:
        company.is_internal = True
        company.save(update_fields=["is_internal"])

    internal_roles = SecurityRole.objects.filter(scope__in=["GLOBAL", "INTERNAL"])
    fallback_role = SecurityRole.objects.filter(code="admin_global").first()
    for user in User.objects.filter(empresa__isnull=True, role__in=["GLOBAL", "LABORATORISTA"]):
        user.empresa = company
        user.save(update_fields=["empresa"])
        role = internal_roles.filter(legacy_role=user.role).first() or fallback_role
        if role:
            UserCompanyProfile.objects.update_or_create(
                user=user,
                empresa=company,
                defaults={
                    "role": role,
                    "is_company_admin": user.role == "GLOBAL",
                    "status": "ACTIVE" if user.is_active else "PENDING",
                },
            )


class Migration(migrations.Migration):
    dependencies = [("users", "0018_grant_report_workflow_to_laboratorista"), ("misc", "0047_empresa_is_internal")]

    operations = [migrations.RunPython(establish_global_oil_company, migrations.RunPython.noop)]

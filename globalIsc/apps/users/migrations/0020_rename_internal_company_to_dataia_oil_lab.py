from django.db import migrations


def rename_internal_company(apps, schema_editor):
    Empresa = apps.get_model("misc", "Empresa")
    Empresa.objects.filter(nit="GLOBAL-OIL-INTERNAL").update(nombre="DATAIA Oil Lab")


class Migration(migrations.Migration):
    dependencies = [("users", "0019_global_oil_internal_company")]

    operations = [migrations.RunPython(rename_internal_company, migrations.RunPython.noop)]

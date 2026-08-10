from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_restrict_company_role_permissions"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="firma_predeterminada",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="firmas_usuarios/",
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("misc", "0045_catalog_versions"),
    ]

    operations = [
        migrations.AddField(
            model_name="pruebafuentelimite",
            name="idempotency_key",
            field=models.CharField(blank=True, max_length=64, null=True, unique=True),
        ),
    ]

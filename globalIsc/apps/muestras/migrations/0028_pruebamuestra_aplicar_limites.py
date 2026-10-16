from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("muestras", "0027_normalize_limit_source_versions"),
    ]

    operations = [
        migrations.AddField(
            model_name="pruebamuestra",
            name="aplicar_limites",
            field=models.BooleanField(
                default=True,
                help_text="Define si esta asignación se evalúa contra límites o solo registra resultados.",
            ),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("muestras", "0021_cleanup_legacy_limits"),
    ]

    operations = [
        migrations.AddField(
            model_name="pruebamuestra",
            name="configuracion_resultados",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Unidad y condicion aplicadas por cada resultado de la prueba.",
            ),
        ),
    ]

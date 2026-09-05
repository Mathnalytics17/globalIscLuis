from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("misc", "0042_remove_predefined_batch_usage"),
    ]

    operations = [
        migrations.AddField(
            model_name="lotepruebaspredefinidodetalle",
            name="configuracion_resultados",
            field=models.JSONField(
                blank=True,
                default=dict,
                help_text="Unidad y condicion predefinidas por resultado de la prueba.",
            ),
        ),
    ]

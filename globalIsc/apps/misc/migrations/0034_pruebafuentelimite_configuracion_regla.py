from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("misc", "0033_lotepruebaspredefinidodetalle_criterio_valor_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="pruebafuentelimite",
            name="configuracion_regla",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="pruebafuentelimite",
            name="politica_evaluacion",
            field=models.CharField(
                choices=[
                    ("todas_deben_cumplir", "Todas deben cumplir"),
                    ("alguna_debe_cumplir", "Al menos una debe cumplir"),
                    ("cantidad_minima", "Cantidad mínima de campos"),
                    ("campos_requeridos", "Deben cumplir campos especificos"),
                    ("peso_minimo", "Puntaje minimo de cumplimiento"),
                    ("solo_informativo", "Solo informativo"),
                ],
                default="todas_deben_cumplir",
                max_length=30,
            ),
        ),
    ]

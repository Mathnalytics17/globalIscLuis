from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("misc", "0027_pruebalimitecampo_evaluacion_opciones"),
    ]

    operations = [
        migrations.AddField(
            model_name="lotepruebaspredefinidodetalle",
            name="criterio_limite_valor",
            field=models.CharField(
                blank=True,
                help_text="Valor de criterio preseleccionado para pruebas booleanas, de opcion o globales simples.",
                max_length=120,
                null=True,
            ),
        ),
    ]

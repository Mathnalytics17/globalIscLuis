from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("muestras", "0014_pruebamuestra_criterio_limite_escala_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="pruebamuestra",
            name="criterio_limite_valor",
            field=models.CharField(
                blank=True,
                help_text="Valor de criterio elegido al asignar la prueba. Se usa para booleanos, opciones y criterios globales simples.",
                max_length=120,
                null=True,
            ),
        ),
    ]

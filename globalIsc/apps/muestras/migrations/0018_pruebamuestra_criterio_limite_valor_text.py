from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("muestras", "0017_rename_muestras_mu_muestra_1ec2f8_idx_muestras_mu_muestra_8645c2_idx"),
    ]

    operations = [
        migrations.AlterField(
            model_name="pruebamuestra",
            name="criterio_limite_valor",
            field=models.TextField(
                blank=True,
                help_text="Criterio elegido al asignar la prueba. Acepta valor simple o JSON con valores por campo de limite.",
                null=True,
            ),
        ),
    ]

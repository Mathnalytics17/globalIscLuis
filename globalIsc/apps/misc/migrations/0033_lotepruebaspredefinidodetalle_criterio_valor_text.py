from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("misc", "0032_alter_extrafield_unique_together_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lotepruebaspredefinidodetalle",
            name="criterio_limite_valor",
            field=models.TextField(
                blank=True,
                help_text="Criterio preseleccionado. Acepta valor simple o JSON con valores por campo de limite.",
                null=True,
            ),
        ),
    ]

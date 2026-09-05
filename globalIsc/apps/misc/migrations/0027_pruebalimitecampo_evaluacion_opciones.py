# Generated for Phase 2.2 evaluation maps

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('misc', '0026_lotepruebaspredefinidodetalle_criterio_limite_escala_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='pruebalimitecampo',
            name='evaluacion_opciones',
            field=models.JSONField(blank=True, null=True),
        ),
    ]

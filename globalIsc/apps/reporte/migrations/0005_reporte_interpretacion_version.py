# Generated manually for the traceability branch.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reporte", "0004_reporteenvio_alter_reporte_options_and_more"),
        ("resultado", "0006_versioninterpretacion"),
    ]

    operations = [
        migrations.AddField(
            model_name="reporte",
            name="interpretacion_version",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="reportes_generados",
                to="resultado.versioninterpretacion",
            ),
        ),
    ]

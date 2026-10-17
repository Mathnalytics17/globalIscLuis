# Generated manually for the traceability branch.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("muestras", "0028_pruebamuestra_aplicar_limites"),
        ("resultado", "0005_optimize_workflow_queries"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="VersionInterpretacion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.PositiveIntegerField()),
                ("contenido", models.JSONField(default=dict)),
                ("motivo", models.TextField(blank=True, default="")),
                ("origen", models.CharField(choices=[("manual", "Manual"), ("importacion", "Importación"), ("ia", "Asistente IA"), ("legado", "Histórico previo")], default="manual", max_length=20)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("creado_por", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="interpretaciones_versionadas", to=settings.AUTH_USER_MODEL)),
                ("muestra", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="versiones_interpretacion", to="muestras.muestra")),
            ],
            options={"ordering": ["-version", "-id"]},
        ),
        migrations.AddConstraint(
            model_name="versioninterpretacion",
            constraint=models.UniqueConstraint(fields=("muestra", "version"), name="resultado_version_interpretacion_unica"),
        ),
        migrations.AddIndex(
            model_name="versioninterpretacion",
            index=models.Index(fields=["muestra", "creado_en"], name="resultado_v_muestra_48ce8d_idx"),
        ),
        migrations.AddIndex(
            model_name="versioninterpretacion",
            index=models.Index(fields=["origen", "creado_en"], name="resultado_v_origen_b3ef20_idx"),
        ),
    ]

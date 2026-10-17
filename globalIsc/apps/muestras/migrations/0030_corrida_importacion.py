from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("muestras", "0029_evento_auditoria_operativa")]

    operations = [
        migrations.CreateModel(
            name="CorridaImportacion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creado_en", models.DateTimeField(auto_now_add=True)), ("finalizado_en", models.DateTimeField(blank=True, null=True)),
                ("tipo", models.CharField(default="migracion_historica", max_length=60)), ("estado", models.CharField(choices=[("borrador", "Borrador"), ("validada", "Validada"), ("aplicada", "Aplicada"), ("parcial", "Aplicada parcialmente"), ("fallida", "Fallida"), ("revertida", "Revertida")], default="borrador", max_length=16)),
                ("archivo_nombre", models.CharField(blank=True, default="", max_length=255)), ("archivo_referencia", models.CharField(blank=True, default="", max_length=500)), ("checksum", models.CharField(blank=True, default="", max_length=128)),
                ("total_filas", models.PositiveIntegerField(default=0)), ("creadas", models.PositiveIntegerField(default=0)), ("actualizadas", models.PositiveIntegerField(default=0)), ("omitidas", models.PositiveIntegerField(default=0)), ("errores", models.PositiveIntegerField(default=0)),
                ("advertencias", models.JSONField(blank=True, default=list)), ("detalle_errores", models.JSONField(blank=True, default=list)), ("metadata", models.JSONField(blank=True, default=dict)), ("reversible", models.BooleanField(default=False)), ("revertida_en", models.DateTimeField(blank=True, null=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="corridas_importacion", to="users.user")), ("empresa", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="corridas_importacion", to="misc.empresa")),
            ], options={"ordering": ["-creado_en", "-id"]},
        ),
        migrations.AddIndex(model_name="corridaimportacion", index=models.Index(fields=["empresa", "creado_en"], name="muestras_co_empresa_5c9448_idx")),
        migrations.AddIndex(model_name="corridaimportacion", index=models.Index(fields=["estado", "creado_en"], name="muestras_co_estado_cab278_idx")),
    ]

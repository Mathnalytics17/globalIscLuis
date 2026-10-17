# Generated manually because the local host does not include the backend's
# Django REST Framework dependency. Keep this migration equivalent to the
# EventoAuditoriaOperativa model.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("activesTree", "0013_global_lubricant_catalog"),
        ("misc", "0046_pruebafuentelimite_idempotency_key"),
        ("muestras", "0028_pruebamuestra_aplicar_limites"),
        ("reporte", "0004_reporteenvio_alter_reporte_options_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EventoAuditoriaOperativa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creado_en", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("tipo_entidad", models.CharField(db_index=True, max_length=40)),
                ("entidad_id", models.CharField(db_index=True, max_length=80)),
                ("entidad_etiqueta", models.CharField(blank=True, default="", max_length=255)),
                ("accion", models.CharField(db_index=True, max_length=100)),
                ("detalle", models.TextField(blank=True, default="")),
                ("motivo", models.TextField(blank=True, default="")),
                ("estado_anterior", models.JSONField(blank=True, default=dict)),
                ("estado_nuevo", models.JSONField(blank=True, default=dict)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("origen", models.CharField(choices=[("ui", "Interfaz"), ("api", "API"), ("importacion", "Importación"), ("proceso", "Proceso automático"), ("ia", "Asistente IA")], default="ui", max_length=20)),
                ("correlation_id", models.CharField(blank=True, db_index=True, default="", max_length=64)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="eventos_operativos", to=settings.AUTH_USER_MODEL)),
                ("empresa", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="eventos_operativos", to="misc.empresa")),
                ("lote", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="eventos_auditoria", to="muestras.lotemuestras")),
                ("maquina", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="eventos_auditoria", to="activesTree.maquina")),
                ("muestra", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="eventos_auditoria", to="muestras.muestra")),
                ("prueba_muestra", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="eventos_auditoria", to="muestras.pruebamuestra")),
                ("punto_muestreo", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="eventos_auditoria", to="activesTree.puntomuestreo")),
                ("reporte", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="eventos_auditoria", to="reporte.reporte")),
            ],
            options={"ordering": ["-creado_en", "-id"]},
        ),
        migrations.AddIndex(model_name="eventoauditoriaoperativa", index=models.Index(fields=["empresa", "creado_en"], name="muestras_e_empresa_1cac08_idx")),
        migrations.AddIndex(model_name="eventoauditoriaoperativa", index=models.Index(fields=["lote", "creado_en"], name="muestras_e_lote_id_845f3d_idx")),
        migrations.AddIndex(model_name="eventoauditoriaoperativa", index=models.Index(fields=["muestra", "creado_en"], name="muestras_e_muestra__947b98_idx")),
        migrations.AddIndex(model_name="eventoauditoriaoperativa", index=models.Index(fields=["maquina", "creado_en"], name="muestras_e_maquina__38cac3_idx")),
        migrations.AddIndex(model_name="eventoauditoriaoperativa", index=models.Index(fields=["tipo_entidad", "entidad_id", "creado_en"], name="muestras_e_tipo_en_473424_idx")),
        migrations.AddIndex(model_name="eventoauditoriaoperativa", index=models.Index(fields=["accion", "creado_en"], name="muestras_e_accion_9f27c5_idx")),
    ]

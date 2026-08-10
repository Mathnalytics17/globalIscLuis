from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("misc", "0029_sample_fields_evaluation_criteria"),
        ("muestras", "0015_pruebamuestra_criterio_limite_valor"),
    ]

    operations = [
        migrations.AddField(
            model_name="muestraatributotecnico",
            name="campo_tecnico",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="atributos_muestra", to="misc.campotecnicomuestra"),
        ),
        migrations.AddField(
            model_name="pruebamuestra",
            name="criterio_evaluacion",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="pruebas_muestra", to="misc.criterioevaluacionlimite"),
        ),
        migrations.RemoveConstraint(
            model_name="muestraatributotecnico",
            name="unique_sample_dynamic_catalog_attribute",
        ),
        migrations.AddConstraint(
            model_name="muestraatributotecnico",
            constraint=models.UniqueConstraint(fields=("muestra", "campo_tecnico"), name="unique_sample_dynamic_field_attribute"),
        ),
        migrations.AddIndex(
            model_name="muestraatributotecnico",
            index=models.Index(fields=["muestra", "campo_tecnico"], name="muestras_mu_muestra_1ec2f8_idx"),
        ),
    ]

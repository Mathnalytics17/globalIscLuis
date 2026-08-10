from django.db import migrations, models


def clean_legacy_decisions(apps, schema_editor):
    Source = apps.get_model("misc", "PruebaFuenteLimite")
    legacy = {
        "campos_requeridos", "criticos", "pesos", "peso_minimo",
        "puntaje_minimo", "umbral_peso_fallado", "fallo_critico_rechaza",
        "regla", "politica", "cantidad",
    }
    for source in Source.objects.all().iterator():
        config = dict(source.configuracion_regla or {})
        for key in legacy:
            config.pop(key, None)
        config["modo"] = "semaforo"
        config["version"] = 2
        config.setdefault("amarillos_para_critico", None)
        source.configuracion_regla = config
        source.politica_evaluacion = "todas_deben_cumplir"
        source.minimo_campos_cumplidos = None
        source.reglas_resultados = {}
        source.save(update_fields=[
            "configuracion_regla",
            "politica_evaluacion",
            "minimo_campos_cumplidos",
            "reglas_resultados",
        ])


class Migration(migrations.Migration):
    dependencies = [
        ("misc", "0039_result_unit_contract"),
    ]

    operations = [
        migrations.RunPython(clean_legacy_decisions, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="pruebafuentelimite",
            name="politica_evaluacion",
            field=models.CharField(
                choices=[
                    ("todas_deben_cumplir", "Todas deben cumplir"),
                    ("solo_informativo", "Solo informativo"),
                ],
                default="todas_deben_cumplir",
                max_length=30,
            ),
        ),
    ]

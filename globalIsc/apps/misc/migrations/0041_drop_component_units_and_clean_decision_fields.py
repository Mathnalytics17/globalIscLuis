from django.db import migrations


def clean_decision_fields(apps, schema_editor):
    Source = apps.get_model("misc", "PruebaFuenteLimite")
    for source in Source.objects.all().iterator():
        config = dict(source.configuracion_regla or {})
        fields = config.get("campos")
        if isinstance(fields, list):
            clean = []
            for field in fields:
                if not isinstance(field, dict):
                    continue
                item = dict(field)
                for key in ["peso", "critico", "requerido"]:
                    item.pop(key, None)
                clean.append(item)
            config["campos"] = clean
        source.configuracion_regla = config
        source.save(update_fields=["configuracion_regla"])


class Migration(migrations.Migration):
    dependencies = [
        ("misc", "0040_remove_weighted_limit_policy"),
    ]

    operations = [
        migrations.RunPython(clean_decision_fields, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="pruebaresultadocomponente",
            name="unidad_catalogo",
        ),
        migrations.RemoveField(
            model_name="pruebaresultadocomponente",
            name="unidad_medida",
        ),
    ]

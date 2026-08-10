from django.db import migrations


LEGACY_KEYS = {
    "amarillos_para_critico",
    "resultados_amarillos_para_critico",
}


def remove_yellow_escalation_thresholds(apps, schema_editor):
    PruebaFuenteLimite = apps.get_model("misc", "PruebaFuenteLimite")
    for source in PruebaFuenteLimite.objects.all().iterator():
        config = dict(source.configuracion_regla or {})
        changed = False
        for key in LEGACY_KEYS:
            if key in config:
                config.pop(key, None)
                changed = True

        result_rules = source.reglas_resultados or {}
        if result_rules:
            result_rules = {}
            changed = True

        if changed:
            source.configuracion_regla = config
            source.reglas_resultados = result_rules
            source.save(update_fields=["configuracion_regla", "reglas_resultados"])


class Migration(migrations.Migration):
    dependencies = [("misc", "0043_lote_detalle_result_config")]

    operations = [
        migrations.RunPython(remove_yellow_escalation_thresholds, migrations.RunPython.noop),
    ]

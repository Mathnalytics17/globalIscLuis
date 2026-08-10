from django.db import migrations, models
import django.db.models.deletion


def move_units_to_results(apps, schema_editor):
    Result = apps.get_model("misc", "PruebaResultado")
    Component = apps.get_model("misc", "PruebaResultadoComponente")

    for result in Result.objects.select_related("prueba").all().iterator():
        components = Component.objects.filter(
            division__resultado=result,
            activo=True,
        ).order_by("orden", "id")
        first = (
            components.exclude(unidad_catalogo_id=None).first()
            or components.exclude(unidad_medida__isnull=True).exclude(unidad_medida="").first()
        )
        result.unidad_catalogo_id = (
            getattr(first, "unidad_catalogo_id", None)
            or getattr(result.prueba, "unidad_catalogo_id", None)
        )
        result.unidad_medida = (
            getattr(first, "unidad_medida", None)
            or getattr(result.prueba, "unidad_medida", None)
        )
        result.save(update_fields=["unidad_catalogo", "unidad_medida"])


class Migration(migrations.Migration):
    dependencies = [
        ("misc", "0038_backfill_scale_components_from_test_contract"),
    ]

    operations = [
        migrations.AddField(
            model_name="pruebaresultado",
            name="unidad_catalogo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="resultados_prueba",
                to="misc.unidad",
            ),
        ),
        migrations.AddField(
            model_name="pruebaresultado",
            name="unidad_medida",
            field=models.CharField(blank=True, max_length=40, null=True),
        ),
        migrations.RunPython(move_units_to_results, migrations.RunPython.noop),
    ]

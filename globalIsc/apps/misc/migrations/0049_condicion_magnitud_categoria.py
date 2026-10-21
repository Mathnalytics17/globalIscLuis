from django.db import migrations, models
import django.db.models.deletion


def backfill_condition_magnitudes(apps, schema_editor):
    CategoriaUnidad = apps.get_model("misc", "CategoriaUnidad")
    Condicion = apps.get_model("misc", "Condicion")

    for condition in Condicion.objects.filter(magnitud_categoria__isnull=True).select_related("unidad__categoria").iterator():
        label = " ".join((condition.magnitud or "").split())
        category = None
        if label:
            category = CategoriaUnidad.objects.filter(nombre__iexact=label).first()
        if category is None and condition.unidad_id and condition.unidad.categoria_id:
            category = condition.unidad.categoria
        if category is None:
            category, _ = CategoriaUnidad.objects.get_or_create(
                nombre=label or "General",
                defaults={"activo": True},
            )
        condition.magnitud_categoria = category
        condition.magnitud = category.nombre
        condition.save(update_fields=["magnitud_categoria", "magnitud"])


class Migration(migrations.Migration):
    dependencies = [("misc", "0048_categoria_unidad")]

    operations = [
        migrations.AddField(
            model_name="condicion",
            name="magnitud_categoria",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="condiciones",
                to="misc.categoriaunidad",
            ),
        ),
        migrations.RunPython(backfill_condition_magnitudes, migrations.RunPython.noop),
    ]

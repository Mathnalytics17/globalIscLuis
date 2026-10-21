from django.db import migrations, models
import django.db.models.deletion
import django.db.models.functions.text


def backfill_unit_categories(apps, schema_editor):
    CategoriaUnidad = apps.get_model("misc", "CategoriaUnidad")
    Unidad = apps.get_model("misc", "Unidad")

    for unit in Unidad.objects.filter(categoria__isnull=True).iterator():
        label = " ".join((unit.magnitud or "General").split()) or "General"
        category = CategoriaUnidad.objects.filter(nombre__iexact=label).first()
        if category is None:
            category = CategoriaUnidad.objects.create(nombre=label, activo=True)
        unit.categoria = category
        # Preserve one canonical label even when legacy data had different
        # casing or accidental whitespace for the same category.
        unit.magnitud = category.nombre
        unit.save(update_fields=["categoria", "magnitud"])


class Migration(migrations.Migration):
    dependencies = [("misc", "0047_empresa_is_internal")]

    operations = [
        migrations.CreateModel(
            name="CategoriaUnidad",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=80)),
                ("descripcion", models.TextField(blank=True, null=True)),
                ("activo", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["nombre"]},
        ),
        migrations.AddConstraint(
            model_name="categoriaunidad",
            constraint=models.UniqueConstraint(django.db.models.functions.text.Lower("nombre"), name="misc_categoria_unidad_nombre_ci_unique"),
        ),
        migrations.AddField(
            model_name="unidad",
            name="categoria",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="unidades", to="misc.categoriaunidad"),
        ),
        migrations.RunPython(backfill_unit_categories, migrations.RunPython.noop),
    ]

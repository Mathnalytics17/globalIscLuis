from decimal import Decimal

from django.db import migrations, models
import django.db.models.deletion


def seed_units_and_conditions(apps, schema_editor):
    Unidad = apps.get_model("misc", "Unidad")
    Condicion = apps.get_model("misc", "Condicion")

    units = [
        ("Centistokes", "cSt", "viscosidad"),
        ("Grados Celsius", "°C", "temperatura"),
        ("Partes por millon", "ppm", "concentracion"),
        ("Mililitros", "ml", "volumen"),
        ("Porcentaje", "%", "porcentaje"),
        ("Miligramo KOH por gramo", "mg KOH/g", "acidez"),
        ("Gramo por centimetro cubico", "g/cm3", "densidad"),
        ("Absorbancia por centimetro", "Abs/cm", "absorbancia"),
        ("Horas", "horas", "tiempo"),
        ("Kilometros", "km", "distancia"),
        ("Dias", "dias", "tiempo"),
    ]

    by_symbol = {}
    for nombre, simbolo, magnitud in units:
        unit, _ = Unidad.objects.update_or_create(
            simbolo=simbolo,
            defaults={
                "nombre": nombre,
                "magnitud": magnitud,
                "activo": True,
            },
        )
        by_symbol[simbolo] = unit

    celsius = by_symbol.get("°C")
    if not celsius:
        return

    for value in [15, 25, 40, 100]:
        Condicion.objects.update_or_create(
            nombre=f"Temperatura {value} C",
            magnitud="temperatura",
            valor=Decimal(value),
            unidad=celsius,
            defaults={
                "descripcion": f"Condicion de ensayo a {value} °C.",
                "activo": True,
            },
        )


def unseed_units_and_conditions(apps, schema_editor):
    # No borramos catálogos maestros en reversa: pueden haber sido usados por pruebas.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("misc", "0018_empresa_nit"),
    ]

    operations = [
        migrations.AddField(
            model_name="prueba",
            name="condicion_catalogo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="pruebas",
                to="misc.condicion",
            ),
        ),
        migrations.AddField(
            model_name="prueba",
            name="unidad_catalogo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="pruebas",
                to="misc.unidad",
            ),
        ),
        migrations.AddField(
            model_name="tipogestionmuestra",
            name="pruebas_sugeridas",
            field=models.ManyToManyField(
                blank=True,
                related_name="tipos_gestion_sugeridos",
                to="misc.prueba",
            ),
        ),
        migrations.RunPython(seed_units_and_conditions, unseed_units_and_conditions),
    ]

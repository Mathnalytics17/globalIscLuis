from django.db import migrations


FIELD_CONFIGS = [
    {
        "tipo_muestra": "aceite",
        "codigo": "grado_viscosidad",
        "nombre_visible": "Grado de viscosidad",
        "orden": 1,
        "catalog_codes": ["grado_viscosidad", "grado_de_viscosidad"],
        "catalog_names": ["grado de viscosidad"],
    },
    {
        "tipo_muestra": "aceite",
        "codigo": "nivel_desempeno",
        "nombre_visible": "Nivel de desempeno",
        "orden": 2,
        "catalog_codes": ["nivel_desempeno", "nivel_de_desempeno"],
        "catalog_names": ["nivel de desempeno", "nivel de desempeño"],
    },
    {
        "tipo_muestra": "aceite",
        "codigo": "uso",
        "nombre_visible": "Uso",
        "orden": 3,
        "catalog_codes": ["uso"],
        "catalog_names": ["uso"],
    },
    {
        "tipo_muestra": "grasa",
        "codigo": "nlgi",
        "nombre_visible": "NLGI",
        "orden": 1,
        "catalog_codes": ["nlgi"],
        "catalog_names": ["nlgi"],
    },
]


def _find_catalog(CatalogoTecnico, config):
    catalog = CatalogoTecnico.objects.filter(
        codigo__in=config["catalog_codes"],
        deleted_at__isnull=True,
    ).first()
    if catalog:
        return catalog

    for name in config["catalog_names"]:
        catalog = CatalogoTecnico.objects.filter(
            nombre__iexact=name,
            deleted_at__isnull=True,
        ).first()
        if catalog:
            return catalog
    return None


def forwards(apps, schema_editor):
    CatalogoTecnico = apps.get_model("misc", "CatalogoTecnico")
    CampoTecnicoMuestra = apps.get_model("misc", "CampoTecnicoMuestra")

    for config in FIELD_CONFIGS:
        catalog = _find_catalog(CatalogoTecnico, config)
        if not catalog:
            continue

        if catalog.tipo_muestra != config["tipo_muestra"]:
            catalog.tipo_muestra = config["tipo_muestra"]
            catalog.save(update_fields=["tipo_muestra"])

        CampoTecnicoMuestra.objects.update_or_create(
            tipo_muestra=config["tipo_muestra"],
            codigo=config["codigo"],
            defaults={
                "nombre_visible": config["nombre_visible"],
                "catalogo": catalog,
                "obligatorio": True,
                "permite_desconocido": True,
                "visible_en_ingreso": True,
                "visible_en_asignacion": True,
                "orden": config["orden"],
                "activo": True,
                "deleted_at": None,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("misc", "0030_backfill_sample_technical_fields"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]

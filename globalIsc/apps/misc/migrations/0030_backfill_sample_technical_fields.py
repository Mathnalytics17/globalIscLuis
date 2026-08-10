from django.db import migrations


DEFAULT_SAMPLE_FIELDS = [
    ("aceite", "grado_viscosidad", "Grado de viscosidad", 1),
    ("aceite", "nivel_desempeno", "Nivel de desempeno", 2),
    ("aceite", "uso", "Uso", 3),
    ("grasa", "nlgi", "NLGI", 1),
]


def forwards(apps, schema_editor):
    CatalogoTecnico = apps.get_model("misc", "CatalogoTecnico")
    CampoTecnicoMuestra = apps.get_model("misc", "CampoTecnicoMuestra")

    for tipo_muestra, codigo, nombre_visible, orden in DEFAULT_SAMPLE_FIELDS:
        catalogo = CatalogoTecnico.objects.filter(
            codigo=codigo,
            deleted_at__isnull=True,
        ).first()
        if not catalogo:
            continue

        CampoTecnicoMuestra.objects.update_or_create(
            tipo_muestra=tipo_muestra,
            codigo=codigo,
            defaults={
                "nombre_visible": nombre_visible,
                "catalogo": catalogo,
                "obligatorio": True,
                "permite_desconocido": True,
                "visible_en_ingreso": True,
                "visible_en_asignacion": True,
                "orden": orden,
                "activo": True,
                "deleted_at": None,
            },
        )


def backwards(apps, schema_editor):
    CampoTecnicoMuestra = apps.get_model("misc", "CampoTecnicoMuestra")
    for tipo_muestra, codigo, _, _ in DEFAULT_SAMPLE_FIELDS:
        CampoTecnicoMuestra.objects.filter(
            tipo_muestra=tipo_muestra,
            codigo=codigo,
        ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("misc", "0029_sample_fields_evaluation_criteria"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

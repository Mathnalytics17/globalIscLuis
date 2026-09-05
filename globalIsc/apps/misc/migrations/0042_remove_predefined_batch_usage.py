from django.db import migrations, models


def convert_usage_templates(apps, schema_editor):
    Template = apps.get_model("misc", "LotePruebasPredefinido")
    Template.objects.filter(tipo_lote="uso").update(
        tipo_lote="personalizado",
        es_default=False,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("misc", "0041_drop_component_units_and_clean_decision_fields"),
    ]

    operations = [
        migrations.RunPython(convert_usage_templates, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="lotepruebaspredefinido",
            name="uso_referencia",
        ),
        migrations.AlterField(
            model_name="lotepruebaspredefinido",
            name="tipo_lote",
            field=models.CharField(
                choices=[
                    ("gestion", "Por gestión"),
                    ("personalizado", "Personalizado"),
                ],
                default="personalizado",
                max_length=20,
            ),
        ),
    ]

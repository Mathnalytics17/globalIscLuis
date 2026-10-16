from django.db import migrations, models


def merge_global_duplicates(apps, schema_editor):
    Lubricante = apps.get_model('activesTree', 'Lubricante')
    PuntoMuestreo = apps.get_model('activesTree', 'PuntoMuestreo')

    keepers = {}
    for lubricant in Lubricante.objects.order_by('id'):
        identity = (lubricant.fabricante, lubricant.referencia)
        keeper = keepers.get(identity)
        if keeper is None:
            keepers[identity] = lubricant
            continue
        PuntoMuestreo.objects.filter(lubricante_catalogo_id=lubricant.id).update(
            lubricante_catalogo_id=keeper.id,
            lubricante=keeper.nombre,
        )
        lubricant.delete()


class Migration(migrations.Migration):
    dependencies = [('activesTree', '0012_lubricant_identity')]

    operations = [
        migrations.RemoveConstraint(
            model_name='lubricante',
            name='unique_lubricant_per_company_manufacturer_reference',
        ),
        migrations.RunPython(merge_global_duplicates, migrations.RunPython.noop),
        migrations.RemoveField(model_name='lubricante', name='empresa'),
        migrations.AddConstraint(
            model_name='lubricante',
            constraint=models.UniqueConstraint(
                fields=('fabricante', 'referencia'),
                name='unique_global_lubricant_manufacturer_reference',
            ),
        ),
    ]

from django.db import migrations, models
from django.db.models import Count, Q


def merge_duplicate_machine_nodes(apps, schema_editor):
    Carpeta = apps.get_model('activesTree', 'Carpeta')
    Maquina = apps.get_model('activesTree', 'Maquina')

    duplicate_machine_ids = (
        Carpeta.objects.exclude(machine_id__isnull=True)
        .values('machine_id')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
        .values_list('machine_id', flat=True)
    )
    for machine_id in duplicate_machine_ids.iterator():
        machine = Maquina.objects.get(pk=machine_id)
        root = Carpeta.objects.filter(
            compania_id=machine.empresa_id,
            typeFolder='root',
            id_parent_node='-1',
        ).order_by('id').first()
        root_id = str(root.id) if root else None
        nodes = list(Carpeta.objects.filter(machine_id=machine_id).order_by('id'))
        # Preserve a customer-organized position rather than an automatic
        # direct child of the root when legacy imports created both.
        keep = min(
            nodes,
            key=lambda node: (str(node.id_parent_node) == root_id, node.id),
        )
        for duplicate in nodes:
            if duplicate.pk == keep.pk:
                continue
            Carpeta.objects.filter(id_parent_node=str(duplicate.pk)).update(
                id_parent_node=str(keep.pk)
            )
            duplicate.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('activesTree', '0013_global_lubricant_catalog'),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_machine_nodes, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='carpeta',
            constraint=models.UniqueConstraint(
                condition=Q(machine__isnull=False),
                fields=('machine',),
                name='unique_machine_tree_node',
            ),
        ),
    ]

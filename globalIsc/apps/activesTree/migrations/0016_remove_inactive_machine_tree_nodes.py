from django.db import migrations


def remove_inactive_machine_tree_nodes(apps, schema_editor):
    Carpeta = apps.get_model('activesTree', 'Carpeta')
    inactive_nodes = Carpeta.objects.filter(machine__activo=False).order_by('id')
    for node in inactive_nodes.iterator():
        # A deactivated machine remains available in operational history, but
        # it must not leave an undeletable visual ghost in the active tree.
        Carpeta.objects.filter(id_parent_node=str(node.pk)).update(
            id_parent_node=str(node.id_parent_node)
        )
        node.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('activesTree', '0015_unique_company_root_tree_node'),
    ]

    operations = [
        migrations.RunPython(remove_inactive_machine_tree_nodes, migrations.RunPython.noop),
    ]

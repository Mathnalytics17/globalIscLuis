from django.db import migrations, models
from django.db.models import Count, Q


def merge_duplicate_company_roots(apps, schema_editor):
    Carpeta = apps.get_model('activesTree', 'Carpeta')
    company_ids = (
        Carpeta.objects.filter(typeFolder='root', id_parent_node='-1')
        .values('compania_id')
        .annotate(total=Count('id'))
        .filter(total__gt=1)
        .values_list('compania_id', flat=True)
    )
    for company_id in company_ids.iterator():
        roots = list(Carpeta.objects.filter(
            compania_id=company_id,
            typeFolder='root',
            id_parent_node='-1',
        ).order_by('id'))
        canonical = roots[0]
        for duplicate in roots[1:]:
            Carpeta.objects.filter(id_parent_node=str(duplicate.pk)).update(
                id_parent_node=str(canonical.pk)
            )
            duplicate.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('activesTree', '0014_unique_machine_tree_node'),
    ]

    operations = [
        migrations.RunPython(merge_duplicate_company_roots, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='carpeta',
            constraint=models.UniqueConstraint(
                condition=Q(typeFolder='root', id_parent_node='-1'),
                fields=('compania',),
                name='unique_company_root_tree_node',
            ),
        ),
    ]

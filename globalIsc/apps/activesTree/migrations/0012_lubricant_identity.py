from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('activesTree', '0011_lubricant_catalog')]

    operations = [
        migrations.RemoveConstraint(
            model_name='lubricante', name='unique_lubricant_per_company_identity',
        ),
        migrations.AddConstraint(
            model_name='lubricante',
            constraint=models.UniqueConstraint(
                fields=('empresa', 'fabricante', 'referencia'),
                name='unique_lubricant_per_company_manufacturer_reference',
            ),
        ),
    ]

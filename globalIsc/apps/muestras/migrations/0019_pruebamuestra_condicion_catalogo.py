import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("misc", "0033_lotepruebaspredefinidodetalle_criterio_valor_text"),
        ("muestras", "0018_pruebamuestra_criterio_limite_valor_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="pruebamuestra",
            name="condicion_catalogo",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="pruebas_muestra",
                to="misc.condicion",
            ),
        ),
    ]

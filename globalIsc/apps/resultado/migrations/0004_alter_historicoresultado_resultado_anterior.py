# Generated manually during backend hardening.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("resultado", "0003_historicoresultado_resultado_h_resulta_28b3cd_idx_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="historicoresultado",
            name="resultado_anterior",
            field=models.TextField(),
        ),
    ]

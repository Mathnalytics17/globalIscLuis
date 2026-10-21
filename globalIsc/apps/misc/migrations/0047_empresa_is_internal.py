from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("misc", "0046_pruebafuentelimite_idempotency_key")]

    operations = [
        migrations.AddField(
            model_name="empresa",
            name="is_internal",
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]

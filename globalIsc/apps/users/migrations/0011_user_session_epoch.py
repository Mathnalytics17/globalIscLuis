from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("users", "0007_sampling_point_permissions")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="session_epoch",
            field=models.PositiveIntegerField(default=1),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("users", "0013_traceability_and_report_action_permissions")]

    operations = [
        migrations.AddField(
            model_name="user",
            name="home_path",
            field=models.CharField(blank=True, default="", max_length=160),
        ),
    ]

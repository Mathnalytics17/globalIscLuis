from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="notificationdispatchlog",
            name="attempts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="notificationdispatchlog",
            name="message",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="notificationdispatchlog",
            name="processed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("dashboard", "0002_notification_dispatch_queue")]

    operations = [
        migrations.DeleteModel(name="NotificationDispatchLog"),
        migrations.DeleteModel(name="NotificationTopic"),
    ]

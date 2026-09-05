from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationTopic",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(choices=[("daily_digest", "Resumen operativo diario"), ("new_client_batch", "Nuevo lote ingresado por cliente"), ("due_soon", "Lotes proximos a vencer"), ("overdue", "Lotes vencidos"), ("undesired_result", "Resultados no deseados"), ("report_ready", "Informe listo para enviar"), ("report_sent", "Informe enviado al cliente"), ("config_issue", "Error de flujo o configuracion"), ("incomplete_client_batch", "Lote de cliente incompleto"), ("review_reminder", "Revision pendiente")], max_length=80, unique=True)),
                ("name", models.CharField(max_length=140)),
                ("description", models.TextField(blank=True)),
                ("active", models.BooleanField(db_index=True, default=True)),
                ("email_enabled", models.BooleanField(default=True)),
                ("in_app_enabled", models.BooleanField(default=True)),
                ("send_time", models.TimeField(blank=True, null=True)),
                ("frequency", models.CharField(default="event", max_length=30)),
                ("roles", models.JSONField(blank=True, default=list)),
                ("external_emails", models.JSONField(blank=True, default=list)),
                ("last_sent_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("users", models.ManyToManyField(blank=True, related_name="notification_topics", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["name"],
                "indexes": [models.Index(fields=["code", "active"], name="dashboard_n_code_84b8cd_idx")],
            },
        ),
        migrations.CreateModel(
            name="NotificationDispatchLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_code", models.CharField(db_index=True, max_length=80)),
                ("subject", models.CharField(max_length=180)),
                ("recipients", models.JSONField(blank=True, default=list)),
                ("status", models.CharField(db_index=True, default="sent", max_length=20)),
                ("error", models.TextField(blank=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("topic", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="dispatches", to="dashboard.notificationtopic")),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [models.Index(fields=["event_code", "created_at"], name="dashboard_n_event_c_66af7e_idx"), models.Index(fields=["status", "created_at"], name="dashboard_n_status_9753fe_idx")],
            },
        ),
    ]

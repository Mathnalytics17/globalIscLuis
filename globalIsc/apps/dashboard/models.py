from django.db import models
from django.db.models import Q

from apps.users.api.models.index import User


INTERNAL_RECIPIENT_ROLE = "__GLOBAL_OIL_INTERNAL__"


class NotificationTopic(models.Model):
    class EventCode(models.TextChoices):
        DAILY_DIGEST = "daily_digest", "Resumen operativo diario"
        NEW_CLIENT_BATCH = "new_client_batch", "Nuevo lote ingresado por cliente"
        DUE_SOON = "due_soon", "Lotes proximos a vencer"
        OVERDUE = "overdue", "Lotes vencidos"
        UNDESIRED_RESULT = "undesired_result", "Resultados no deseados"
        REPORT_READY = "report_ready", "Informe listo para enviar"
        REPORT_SENT = "report_sent", "Informe enviado al cliente"
        CONFIG_ISSUE = "config_issue", "Error de flujo o configuracion"
        INCOMPLETE_CLIENT_BATCH = "incomplete_client_batch", "Lote de cliente incompleto"
        REVIEW_REMINDER = "review_reminder", "Revision pendiente"

    code = models.CharField(max_length=80, choices=EventCode.choices, unique=True)
    name = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True, db_index=True)
    email_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    send_time = models.TimeField(blank=True, null=True)
    frequency = models.CharField(max_length=30, default="event")
    roles = models.JSONField(default=list, blank=True)
    external_emails = models.JSONField(default=list, blank=True)
    users = models.ManyToManyField(User, blank=True, related_name="notification_topics")
    last_sent_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["code", "active"]),
        ]

    def __str__(self):
        return self.name

    def resolved_recipient_emails(self):
        """Return the real, deduplicated addresses that will receive this rule."""
        roles = self.roles if isinstance(self.roles, list) else []
        regular_roles = [role for role in roles if role != INTERNAL_RECIPIENT_ROLE]
        users = User.objects.none()
        if INTERNAL_RECIPIENT_ROLE in roles:
            users = users | User.objects.filter(
                Q(empresa__isnull=True) | Q(role=User.Role.GLOBAL),
                is_active=True,
            )
        if regular_roles:
            users = users | User.objects.filter(role__in=regular_roles, is_active=True)

        emails = set(
            users.exclude(email="").filter(email__isnull=False).values_list("email", flat=True)
        )
        emails.update(
            self.users.filter(is_active=True, email__isnull=False)
            .exclude(email="")
            .values_list("email", flat=True)
        )
        external = self.external_emails if isinstance(self.external_emails, list) else []
        emails.update(str(item).strip().lower() for item in external if str(item).strip())
        return sorted(emails)


class NotificationDispatchLog(models.Model):
    topic = models.ForeignKey(NotificationTopic, on_delete=models.SET_NULL, null=True, blank=True, related_name="dispatches")
    event_code = models.CharField(max_length=80, db_index=True)
    subject = models.CharField(max_length=180)
    message = models.TextField(blank=True)
    recipients = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=20, default="sent", db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    error = models.TextField(blank=True)
    payload = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_code", "created_at"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.event_code} - {self.status}"

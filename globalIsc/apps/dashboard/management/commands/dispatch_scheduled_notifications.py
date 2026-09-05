from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.dashboard.api.services.operational_center import send_daily_digest, send_due_batches_digest
from apps.dashboard.models import NotificationTopic
from apps.users.api.models.index import User


class Command(BaseCommand):
    help = "Envía las reglas de correo diarias cuya hora programada ya se cumplió."

    def handle(self, *args, **options):
        now = timezone.localtime()
        today = now.date()
        operator = (
            User.objects.filter(is_active=True, is_superuser=True).order_by("id").first()
            or User.objects.filter(is_active=True, is_staff=True).order_by("id").first()
        )
        if not operator:
            self.stdout.write(self.style.WARNING("No hay un usuario administrativo activo para construir el resumen."))
            return

        topics = NotificationTopic.objects.filter(
            code__in=[
                NotificationTopic.EventCode.DAILY_DIGEST,
                NotificationTopic.EventCode.DUE_SOON,
                NotificationTopic.EventCode.OVERDUE,
            ],
            active=True,
            email_enabled=True,
            frequency="daily",
            send_time__isnull=False,
            send_time__lte=now.time(),
        )
        sent = 0
        for topic in topics:
            if topic.last_sent_at and timezone.localtime(topic.last_sent_at).date() >= today:
                continue
            if topic.code == NotificationTopic.EventCode.DAILY_DIGEST:
                result = send_daily_digest(operator)
            else:
                result = send_due_batches_digest(operator, topic.code)
            if result.get("sent") or result.get("reason") == "no_matches":
                sent += 1

        self.stdout.write(self.style.SUCCESS(f"Reglas diarias procesadas: {sent}"))

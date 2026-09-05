from django.core.management.base import BaseCommand

from apps.dashboard.api.services.operational_center import process_pending_notifications


class Command(BaseCommand):
    help = "Envia las notificaciones pendientes de la cola persistente."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        summary = process_pending_notifications(limit=max(1, options["limit"]))
        self.stdout.write(
            self.style.SUCCESS(
                f"Procesadas: {summary['processed']}; enviadas: {summary['sent']}; "
                f"fallidas: {summary['failed']}."
            )
        )

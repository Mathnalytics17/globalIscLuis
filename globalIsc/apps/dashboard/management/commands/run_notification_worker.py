import time

from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.dashboard.api.services.operational_center import process_pending_notifications


class Command(BaseCommand):
    help = "Procesa continuamente correos por evento y reglas diarias programadas."

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=int, default=30)
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        interval = max(5, options["interval"])
        while True:
            call_command("dispatch_scheduled_notifications")
            summary = process_pending_notifications()
            if summary["processed"]:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Cola procesada: {summary['sent']} enviados, {summary['failed']} fallidos."
                    )
                )
            if options["once"]:
                return
            time.sleep(interval)

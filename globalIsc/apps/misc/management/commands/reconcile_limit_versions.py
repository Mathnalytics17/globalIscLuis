"""Safely publish missing initial limit editions from older demo seeds."""

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.misc.api.models.dynamicTechnicalConfig.index import PruebaFuenteLimite
from apps.misc.api.models.pruebas.index import Prueba


class Command(BaseCommand):
    help = (
        "Publica, sin borrar datos, la versión activa más reciente de cada "
        "prueba que no tenga una versión de límites disponible."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplica la reparación. Sin esta opción solo muestra el diagnóstico.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        apply = options["apply"]
        published = 0
        unresolved = 0

        for prueba in Prueba.objects.filter(activo=True, deleted_at__isnull=True).order_by("id"):
            sources = PruebaFuenteLimite.objects.filter(prueba=prueba, deleted_at__isnull=True)
            available = sources.filter(activo=True, publicada=True)
            if available.count() == 1:
                continue
            if available.count() > 1:
                unresolved += 1
                self.stdout.write(self.style.WARNING(
                    f"{prueba.acronimo}: tiene {available.count()} versiones publicadas; se conserva sin cambios."
                ))
                continue

            candidate = sources.filter(activo=True).order_by("-version", "-id").first()
            if not candidate:
                unresolved += 1
                self.stdout.write(self.style.WARNING(
                    f"{prueba.acronimo}: no tiene una versión activa para publicar."
                ))
                continue

            self.stdout.write(f"{prueba.acronimo}: publicar V{candidate.version}.")
            if apply:
                candidate.publicada = True
                candidate.save(update_fields=["publicada", "updated_at"])
            published += 1

        mode = "aplicada" if apply else "simulada"
        self.stdout.write(self.style.SUCCESS(
            f"Reparación {mode}: {published} versión(es) publicadas, "
            f"{unresolved} caso(s) que requieren revisión."
        ))

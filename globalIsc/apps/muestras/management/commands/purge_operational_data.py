from pathlib import Path
import shutil

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


OPERATIONAL_MODELS = (
    "reporte.ReporteEnvio",
    "reporte.Reporte",
    "resultado.RevisionResultado",
    "resultado.HistoricoResultado",
    "resultado.Resultado",
    "muestras.PruebaMuestra",
    "muestras.MuestraAtributoTecnico",
    "muestras.HistorialMuestra",
    "muestras.IngresoLabLote",
    "muestras.SampleBatchExcelTemplateToken",
    "activesTree.AsignacionPuntoMuestreo",
    "muestras.Muestra",
    "muestras.LoteMuestras",
    "dashboard.NotificationDispatchLog",
)

SECURITY_TRANSIENT_MODELS = (
    "users.UserAuditLog",
    "users.UserInvitation",
    "users.EmailVerificationToken",
    "users.PasswordResetToken",
)


def get_model(label):
    app_label, model_name = label.split(".", 1)
    return apps.get_model(app_label, model_name)


class Command(BaseCommand):
    help = (
        "Elimina datos operativos del laboratorio sin borrar usuarios, empresas, "
        "roles, permisos, pruebas, limites, escalas ni catalogos tecnicos."
    )

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Confirma el borrado.")
        parser.add_argument("--dry-run", action="store_true", help="Solo muestra los conteos.")
        parser.add_argument(
            "--include-security-transients",
            action="store_true",
            help="Tambien elimina invitaciones, tokens y auditoria historica.",
        )
        parser.add_argument(
            "--delete-files",
            action="store_true",
            help="Tambien elimina firmas dibujadas y reportes generados de MEDIA_ROOT.",
        )

    def handle(self, *args, **options):
        labels = list(OPERATIONAL_MODELS)
        if options["include_security_transients"]:
            labels += list(SECURITY_TRANSIENT_MODELS)

        counts = [(label, get_model(label).objects.count()) for label in labels]
        for label, count in counts:
            self.stdout.write(f"{label}: {count}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Simulacion: no se elimino ningun registro."))
            return
        if not options["yes"]:
            raise CommandError("Operacion destructiva. Use --yes o primero revise con --dry-run.")

        with transaction.atomic():
            for label, _ in counts:
                get_model(label).objects.all().delete()

        if options["delete_files"]:
            self._delete_operational_media()

        self.stdout.write(
            self.style.SUCCESS(
                "Datos operativos eliminados. Configuracion tecnica, empresas y seguridad preservadas."
            )
        )

    def _delete_operational_media(self):
        media_root = Path(settings.MEDIA_ROOT).resolve()
        for directory_name in ("firmas", "reportes"):
            target = (media_root / directory_name).resolve()
            if target.parent != media_root:
                raise CommandError(f"Ruta de medios insegura: {target}")
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True, exist_ok=True)
            self.stdout.write(f"Medios operativos limpiados: {target}")

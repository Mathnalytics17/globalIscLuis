"""Reset all operational and technical data while retaining access identities.

This is intentionally narrower than Django's ``flush``: it preserves the
accounts, companies, RBAC matrix and each user's company membership, while
removing every operational, asset and technical-configuration record.
"""

from pathlib import Path
import shutil

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


PRESERVED_MODELS = {
    "users.User",
    "users.SecurityRole",
    "users.SecurityPermission",
    "users.SecurityRolePermission",
    "users.UserCompanyProfile",
    "users.UserDataScopeCompany",
    "misc.Empresa",
    "auth.Group",
    "auth.Permission",
    "contenttypes.ContentType",
}


def reset_models():
    """Every project model except identities, RBAC and companies."""
    return [
        model
        for model in apps.get_models()
        if model._meta.label not in PRESERVED_MODELS
        and model._meta.app_label not in {"auth", "contenttypes"}
    ]


def deletion_order(models):
    """Delete dependent models before their parents, including PROTECT FKs."""
    targets = set(models)
    dependents = {model: set() for model in targets}
    for child in targets:
        for field in child._meta.fields:
            parent = getattr(getattr(field, "remote_field", None), "model", None)
            if parent in targets and parent is not child:
                dependents[parent].add(child)

    ordered, visiting, visited = [], set(), set()

    def visit(model):
        if model in visited or model in visiting:
            return
        visiting.add(model)
        for child in sorted(dependents[model], key=lambda item: item._meta.label):
            visit(child)
        visiting.remove(model)
        visited.add(model)
        ordered.append(model)

    for model in sorted(targets, key=lambda item: item._meta.label):
        visit(model)
    return ordered


class Command(BaseCommand):
    help = (
        "Elimina todos los datos salvo usuarios, empresas, roles, permisos y "
        "las relaciones usuario-empresa. Use primero --dry-run."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Muestra los conteos sin modificar datos.")
        parser.add_argument("--yes", action="store_true", help="Confirma el borrado irreversible.")

    def handle(self, *args, **options):
        models = deletion_order(reset_models())
        counts = [(model, model.objects.count()) for model in models]

        self.stdout.write(self.style.WARNING(
            "Se conservarán: usuarios, empresas, roles, permisos y relaciones usuario-empresa."
        ))
        for model, count in counts:
            self.stdout.write(f"{model._meta.label}: {count}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Simulación: no se eliminó ningún registro."))
            return
        if not options["yes"]:
            raise CommandError("Operación destructiva. Revise --dry-run y confirme con --yes.")

        with transaction.atomic():
            for model, _count in counts:
                model.objects.all().delete()

        self._clear_operational_media()
        self.stdout.write(self.style.SUCCESS(
            "Reinicio completado: solo usuarios, empresas, RBAC y membresías fueron conservados."
        ))

    def _clear_operational_media(self):
        media_root = Path(settings.MEDIA_ROOT).resolve()
        for directory_name in ("firmas", "firmas_usuarios", "reportes", "importaciones"):
            target = (media_root / directory_name).resolve()
            if target.parent != media_root:
                raise CommandError(f"Ruta de medios insegura: {target}")
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True, exist_ok=True)

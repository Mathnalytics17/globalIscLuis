"""Reset the local database while retaining only the Global Oil administrator."""

from pathlib import Path
import shutil

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.misc.api.models.companies.index import Empresa
from apps.users.api.models.index import SecurityRole, User, UserCompanyProfile
from apps.users.api.services import ensure_user_profile


GLOBAL_COMPANY_NIT = "GLOBAL-OIL-INTERNAL"
GLOBAL_ADMIN_EMAIL = "admin@globaloil.local"

PRESERVED_MODELS = {
    "users.User",
    "users.SecurityRole",
    "users.SecurityPermission",
    "users.SecurityRolePermission",
    "misc.Empresa",
    "auth.Group",
    "auth.Permission",
    "contenttypes.ContentType",
}


def reset_models():
    return [
        model
        for model in apps.get_models()
        if model._meta.label not in PRESERVED_MODELS
        and model._meta.app_label not in {"auth", "contenttypes"}
    ]


def deletion_order(models):
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
        "Elimina toda la información local salvo Global Oil interna, "
        "admin@globaloil.local y la matriz RBAC. Use primero --dry-run."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Muestra el alcance sin borrar.")
        parser.add_argument("--yes", action="store_true", help="Confirma el borrado irreversible local.")

    def handle(self, *args, **options):
        global_company = Empresa.objects.filter(nit=GLOBAL_COMPANY_NIT, is_internal=True).first()
        global_admin = User.objects.filter(email=GLOBAL_ADMIN_EMAIL, is_superuser=True).first()
        if not global_company or not global_admin:
            raise CommandError(
                "No existe la línea base requerida (Global Oil interna y admin@globaloil.local superusuario). "
                "No se realizó ningún cambio."
            )

        models = deletion_order(reset_models())
        counts = [(model._meta.label, model.objects.count()) for model in models]
        external_users = User.objects.exclude(pk=global_admin.pk).count()
        external_companies = Empresa.objects.exclude(pk=global_company.pk).count()
        self.stdout.write(self.style.WARNING(
            f"Se conservarán: Empresa {global_company.pk} ({global_company.nombre}), "
            f"usuario {global_admin.pk} ({global_admin.email}) y RBAC."
        ))
        for label, count in counts:
            self.stdout.write(f"{label}: {count}")
        self.stdout.write(f"users.User externos: {external_users}")
        self.stdout.write(f"misc.Empresa externas: {external_companies}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Simulación: no se eliminó ningún registro."))
            return
        if not options["yes"]:
            raise CommandError("Operación destructiva. Revise --dry-run y confirme con --yes.")

        with transaction.atomic():
            for label, _count in counts:
                apps.get_model(label).objects.all().delete()
            User.objects.exclude(pk=global_admin.pk).delete()
            Empresa.objects.exclude(pk=global_company.pk).delete()
            global_admin.empresa = global_company
            global_admin.role = User.Role.GLOBAL
            global_admin.is_active = True
            global_admin.email_verified = True
            global_admin.access_status = User.AccessStatus.ACTIVE
            global_admin.is_read_only = False
            global_admin.data_scope_override = ""
            global_admin.home_path = ""
            global_admin.save()
            ensure_user_profile(
                global_admin,
                global_company,
                role=SecurityRole.objects.get(code="admin_global"),
                is_company_admin=True,
                status=UserCompanyProfile.Status.ACTIVE,
            )

        self._clear_operational_media()
        self.stdout.write(self.style.SUCCESS(
            "Base local limpia. Solo Global Oil, admin@globaloil.local y RBAC permanecen."
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

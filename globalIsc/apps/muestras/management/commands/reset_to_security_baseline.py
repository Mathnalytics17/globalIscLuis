"""Reset a database without deleting accounts or the RBAC configuration.

This command intentionally does not call ``flush``.  A flush would erase
password hashes, user accounts and the role/permission matrix together with the
business data.  Instead it removes the business apps in dependency order and
detaches the preserved users from the deleted companies first.
"""

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.users.api.models.index import User


PRESERVED_MODELS = {
    "users.User",
    "users.SecurityRole",
    "users.SecurityPermission",
    "users.SecurityRolePermission",
    # Django permission metadata is harmless and is required for administration.
    "auth.Group",
    "auth.Permission",
    "contenttypes.ContentType",
}

BUSINESS_APP_LABELS = {
    "activesTree",
    "misc",
    "muestras",
    "reporte",
    "resultado",
    "admin",
    "sessions",
}

USER_SECURITY_TRANSIENT_MODELS = {
    "users.EmailVerificationToken",
    "users.PasswordResetToken",
    "users.UserAuditLog",
    "users.UserCompanyProfile",
    "users.UserDataScopeCompany",
    "users.UserInvitation",
}


def reset_models():
    """All application models to wipe, excluding users and RBAC records."""
    models = []
    for model in apps.get_models():
        label = model._meta.label
        if label in PRESERVED_MODELS:
            continue
        if model._meta.app_label in BUSINESS_APP_LABELS or label in USER_SECURITY_TRANSIENT_MODELS:
            models.append(model)
    return models


def deletion_order(models):
    """Return child-before-parent order while respecting PROTECT foreign keys."""
    target_models = set(models)
    dependents = {model: set() for model in target_models}
    for child in target_models:
        for field in child._meta.fields:
            remote = getattr(getattr(field, "remote_field", None), "model", None)
            if remote in target_models and remote is not child:
                dependents[remote].add(child)

    ordered = []
    visiting = set()
    visited = set()

    def visit(model):
        if model in visited:
            return
        if model in visiting:
            # Los catálogos versionados contienen referencias recíprocas. El
            # ORM puede recolectar esa componente conectada al borrar el primer
            # modelo; romper la recursión conserva el orden para el resto. Si
            # existiera un PROTECT incompatible, el transaction.atomic de
            # abajo abortaría por completo sin dejar una limpieza parcial.
            return
        visiting.add(model)
        for child in sorted(dependents[model], key=lambda item: item._meta.label):
            visit(child)
        visiting.remove(model)
        visited.add(model)
        ordered.append(model)

    for model in sorted(target_models, key=lambda item: item._meta.label):
        visit(model)
    return ordered


class Command(BaseCommand):
    help = (
        "Elimina todos los datos de negocio y conserva solamente usuarios, "
        "roles y permisos RBAC. Use primero --dry-run."
    )

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Muestra lo que se eliminaría sin modificar datos.")
        parser.add_argument("--yes", action="store_true", help="Confirma el restablecimiento destructivo.")

    def handle(self, *args, **options):
        models = deletion_order(reset_models())
        counts = [(model, model.objects.count()) for model in models]

        self.stdout.write(self.style.WARNING("Se conservarán: users.User y la matriz users.Security*."))
        self.stdout.write("Se eliminarán:")
        for model, count in counts:
            self.stdout.write(f"{model._meta.label}: {count}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Simulación: no se eliminó ningún registro."))
            return
        if not options["yes"]:
            raise CommandError("Operación destructiva. Ejecute primero --dry-run y confirme con --yes.")

        with transaction.atomic():
            # A User points to Empresa with SET_NULL, but clearing explicitly
            # makes the preserved account state deterministic after the reset.
            users_updated = User.objects.exclude(empresa__isnull=True).update(
                empresa=None,
                data_scope_override="",
                home_path="",
            )
            for model, _count in counts:
                model.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                "Base restablecida a seguridad: "
                f"{users_updated} usuario(s) quedaron sin empresa, alcance ni inicio personalizado."
            )
        )

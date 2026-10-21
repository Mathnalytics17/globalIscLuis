"""Create the smallest coherent demo tenant baseline after a security reset."""

import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.misc.api.models.companies.index import Empresa
from apps.users.api.models.index import SecurityRole, User, UserCompanyProfile
from apps.users.api.services import ensure_user_profile, seed_default_permissions


GLOBAL_ADMIN_EMAIL = "admin@globaloil.local"
TENANTS = (
    ("Empresa Minera Demo", "MINERA-DEMO", "minera"),
    ("Taller Demo", "TALLER-DEMO", "taller"),
    ("Industria Demo", "INDUSTRIA-DEMO", "industria"),
)
ACCOUNT_TYPES = (
    ("admin", "Administrador", User.Role.ADMIN, "admin_empresa", True),
    ("consulta", "Consulta", User.Role.EMPRESA, "empresa_consulta", False),
    ("muestras", "Carga de muestras", User.Role.EMPRESA, "empresa_carga_muestras", False),
)


class Command(BaseCommand):
    help = (
        "Crea un administrador global y tres empresas demo con tres cuentas "
        "por empresa. Debe ejecutarse sobre una base sin datos de negocio."
    )

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Confirma reemplazar las cuentas no globales.")
        parser.add_argument("--reset-passwords", action="store_true", help="Restablece las contraseñas de todas las cuentas base.")

    @transaction.atomic
    def handle(self, *args, **options):
        if not options["yes"]:
            raise CommandError("Este comando reemplaza cuentas no globales. Confirme con --yes.")

        # The schema migration guarantees Global Oil in every environment. It
        # is part of the security baseline, not business/demo data. Any other
        # company means this command would mix its deterministic seed with
        # existing tenants, so it must stop instead of guessing.
        non_baseline_companies = Empresa.objects.exclude(nit="GLOBAL-OIL-INTERNAL")
        if non_baseline_companies.exists():
            raise CommandError(
                "La base contiene empresas cliente. Ejecute reset_to_security_baseline primero; "
                "este comando no mezcla una base limpia con datos existentes."
            )

        password = os.environ.get("DEMO_DEFAULT_PASSWORD", "")
        if len(password) < 12:
            raise CommandError("Defina DEMO_DEFAULT_PASSWORD con al menos 12 caracteres.")

        seed_default_permissions()
        # A clean base has a single global administrator. This removes stale
        # demo/client users left over from a previous environment.
        UserCompanyProfile.objects.all().delete()
        User.objects.exclude(email=GLOBAL_ADMIN_EMAIL).delete()

        global_company, _ = Empresa.objects.update_or_create(
            nit="GLOBAL-OIL-INTERNAL",
            defaults={
                "nombre": "Global Oil",
                "nit": "GLOBAL-OIL-INTERNAL",
                "email": "contacto@globaloil.local",
                "is_active": True,
                "is_internal": True,
                "status": Empresa.Status.ACTIVE,
            },
        )

        global_admin, created = User.objects.update_or_create(
            email=GLOBAL_ADMIN_EMAIL,
            defaults={
                "first_name": "Administrador",
                "last_name": "Global",
                "role": User.Role.GLOBAL,
                "empresa": global_company,
                "is_active": True,
                "email_verified": True,
                "access_status": User.AccessStatus.ACTIVE,
                "is_read_only": False,
                "is_staff": True,
                "is_superuser": True,
                "home_path": "",
                "data_scope_override": "",
            },
        )
        if created or options["reset_passwords"]:
            global_admin.set_password(password)
            global_admin.save(update_fields=["password"])
        ensure_user_profile(
            global_admin,
            global_company,
            role=SecurityRole.objects.get(code="admin_global"),
            is_company_admin=True,
            status=UserCompanyProfile.Status.ACTIVE,
        )

        accounts_created = 0
        for company_name, nit, domain_key in TENANTS:
            company = Empresa.objects.create(
                nombre=company_name,
                nit=nit,
                email=f"contacto@{domain_key}.demo",
                is_active=True,
                is_internal=False,
                status=Empresa.Status.ACTIVE,
            )
            for local_part, label, legacy_role, role_code, is_company_admin in ACCOUNT_TYPES:
                role = SecurityRole.objects.get(code=role_code)
                user = User.objects.create_user(
                    email=f"{local_part}@{domain_key}.demo",
                    password=password,
                    first_name=label,
                    last_name=company_name.replace(" Demo", ""),
                    role=legacy_role,
                    empresa=company,
                    is_active=True,
                    email_verified=True,
                    access_status=User.AccessStatus.ACTIVE,
                    is_read_only=False,
                )
                profile = ensure_user_profile(
                    user,
                    company,
                    role=role,
                    is_company_admin=is_company_admin,
                    status=UserCompanyProfile.Status.ACTIVE,
                )
                profile.activated_at = timezone.now()
                profile.save(update_fields=["activated_at", "updated_at"])
                accounts_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Base creada: Global Oil interna, 1 administrador global, {len(TENANTS)} empresas cliente y {accounts_created} cuentas de empresa."
        ))

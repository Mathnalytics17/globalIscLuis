import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.misc.api.models.companies.index import Empresa
from apps.users.api.models.index import SecurityRole, User, UserCompanyProfile
from apps.users.api.services import ensure_user_profile, seed_default_permissions


ACCOUNT_DEFINITIONS = (
    {
        "key": "global_admin",
        "email": "admin.global@globaloil.demo",
        "first_name": "Administrador",
        "last_name": "Global",
        "legacy_role": User.Role.GLOBAL,
        "role_code": "admin_global",
        "company": "Global Oil",
        "is_staff": True,
        "is_superuser": True,
        "is_company_admin": True,
    },
    {
        "key": "laboratory",
        "email": "laboratorio@globaloil.demo",
        "first_name": "Usuario",
        "last_name": "Laboratorio",
        "legacy_role": User.Role.LABORATORISTA,
        "role_code": "laboratorista",
        "company": "Global Oil",
    },
    {
        "key": "reviewer",
        "email": "revisor@globaloil.demo",
        "first_name": "Usuario",
        "last_name": "Revisor",
        "legacy_role": User.Role.LABORATORISTA,
        "role_code": "revisor_interpretador",
        "company": "Global Oil",
    },
    {
        "key": "minera_admin",
        "email": "admin@minera.demo",
        "first_name": "Administrador",
        "last_name": "Minera",
        "legacy_role": User.Role.ADMIN,
        "role_code": "admin_empresa",
        "company": "Empresa Minera Demo",
        "is_company_admin": True,
    },
    {
        "key": "minera_query",
        "email": "consulta@minera.demo",
        "first_name": "Consulta",
        "last_name": "Minera",
        "legacy_role": User.Role.EMPRESA,
        "role_code": "empresa_consulta",
        "company": "Empresa Minera Demo",
    },
    {
        "key": "minera_loader",
        "email": "muestras@minera.demo",
        "first_name": "Carga",
        "last_name": "Minera",
        "legacy_role": User.Role.EMPRESA,
        "role_code": "empresa_carga_muestras",
        "company": "Empresa Minera Demo",
    },
    {
        "key": "taller_admin",
        "email": "admin@taller.demo",
        "first_name": "Administrador",
        "last_name": "Taller",
        "legacy_role": User.Role.ADMIN,
        "role_code": "admin_empresa",
        "company": "Taller Demo",
        "is_company_admin": True,
    },
    {
        "key": "taller_read_only",
        "email": "lectura@taller.demo",
        "first_name": "Solo",
        "last_name": "Lectura",
        "legacy_role": User.Role.EMPRESA,
        "role_code": "solo_lectura",
        "company": "Taller Demo",
        "read_only": True,
    },
)


class Command(BaseCommand):
    help = "Crea de forma idempotente permisos, roles, empresas y cuentas iniciales."

    def add_arguments(self, parser):
        parser.add_argument(
            "--with-demo-accounts",
            action="store_true",
            help="Crea las cuentas multiempresa para pruebas funcionales.",
        )
        parser.add_argument(
            "--reset-passwords",
            action="store_true",
            help="Restablece tambien las contrasenas de cuentas ya existentes.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        seed_default_permissions()
        self.stdout.write(self.style.SUCCESS("Roles y permisos sincronizados."))

        if not options["with_demo_accounts"]:
            return

        password = os.environ.get("DEMO_DEFAULT_PASSWORD", "")
        if len(password) < 12:
            raise CommandError(
                "Defina DEMO_DEFAULT_PASSWORD con al menos 12 caracteres. "
                "La contrasena no se guarda en el repositorio."
            )

        companies = {}
        for name, nit in (
            ("Global Oil", "GLOBAL-OIL-DEMO"),
            ("Empresa Minera Demo", "MINERA-DEMO"),
            ("Taller Demo", "TALLER-DEMO"),
        ):
            company, _ = Empresa.objects.update_or_create(
                nombre=name,
                defaults={
                    "nit": nit,
                    "email": f"contacto@{nit.lower()}.test",
                    "is_active": True,
                    "status": Empresa.Status.ACTIVE,
                },
            )
            companies[name] = company

        for definition in ACCOUNT_DEFINITIONS:
            company = companies[definition["company"]]
            user, created = User.objects.update_or_create(
                email=definition["email"],
                defaults={
                    "first_name": definition["first_name"],
                    "last_name": definition["last_name"],
                    "role": definition["legacy_role"],
                    "empresa": company,
                    "is_active": True,
                    "email_verified": True,
                    "access_status": User.AccessStatus.ACTIVE,
                    "is_read_only": definition.get("read_only", False),
                    "is_staff": definition.get("is_staff", False),
                    "is_superuser": definition.get("is_superuser", False),
                },
            )
            if created or options["reset_passwords"]:
                user.set_password(password)
                user.save(update_fields=["password"])

            role = SecurityRole.objects.get(code=definition["role_code"])
            profile = ensure_user_profile(
                user,
                company,
                role=role,
                is_company_admin=definition.get("is_company_admin", False),
                status=UserCompanyProfile.Status.ACTIVE,
            )
            if not profile.activated_at:
                profile.activated_at = timezone.now()
                profile.save(update_fields=["activated_at", "updated_at"])
            self.stdout.write(f"{definition['key']}: {user.email} [{role.code}]")

        self.stdout.write(
            self.style.SUCCESS(
                "Cuentas demo listas. La contrasena procede exclusivamente de DEMO_DEFAULT_PASSWORD."
            )
        )

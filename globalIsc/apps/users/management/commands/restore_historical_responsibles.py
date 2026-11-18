"""Restore authorship metadata from Global Oil historical ETL artifacts.

The legacy OA workbook records the analyst in ``Responsable``.  Historical
reports retain that text as their visible responsible person, while matching
disabled accounts are created only as a traceability directory; they cannot
log in or receive any permissions.
"""
import json
import os
import re
import unicodedata
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.reporte.api.models.index import Reporte
from apps.users.api.models.index import User


def _clean_name(value):
    return " ".join(str(value or "").split())


def _email_for(name):
    normalized = unicodedata.normalize("NFKD", name)
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    slug = re.sub(r"[^a-z0-9]+", ".", normalized.casefold()).strip(".")
    return f"historico.{slug}@globaloil.local"


class Command(BaseCommand):
    help = "Restaura responsables históricos en reportes y crea cuentas inactivas de solo trazabilidad."

    def add_arguments(self, parser):
        parser.add_argument(
            "--artifacts",
            type=Path,
            default=Path("outputs/migracion_historica_global_oil"),
            help="Carpeta de salida del ETL histórico.",
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--password-env",
            default="HISTORICAL_ACCOUNT_PASSWORD",
            help="Variable de entorno con la contraseña común de las cuentas históricas.",
        )

    def handle(self, *args, **options):
        raw_path = options["artifacts"] / "staging" / "reportes_oa_raw.jsonl"
        if not raw_path.is_file():
            raise CommandError(f"No existe el artefacto ETL: {raw_path}")

        responsible_by_oa = {}
        for line in raw_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line).get("data", {})
            responsible = _clean_name(data.get("Responsable"))
            oa = str(data.get("OA") or "").strip()
            if responsible and oa:
                responsible_by_oa[oa] = responsible

        names_from_source = set(responsible_by_oa.values())
        account_password = os.environ.get(options["password_env"], "")
        if names_from_source and not options["dry_run"] and not account_password:
            raise CommandError(
                f"Defina la variable {options['password_env']} para crear las cuentas históricas con una contraseña común."
            )

        report_updates = 0
        names = set()
        for report in Reporte.objects.select_related("muestra").all().iterator():
            metadata = report.muestra.campos_adicionales or {}
            responsible = responsible_by_oa.get(str(metadata.get("oa_origen") or "").strip())
            if not responsible:
                continue
            names.add(responsible)
            if report.Responsable != responsible:
                report_updates += 1
                if not options["dry_run"]:
                    Reporte.objects.filter(pk=report.pk).update(Responsable=responsible)

        created = 0
        existing = 0
        passwords_updated = 0
        for name in sorted(names):
            email = _email_for(name)
            user = User.objects.filter(email=email).first()
            if user:
                existing += 1
                # These addresses are reserved for ETL provenance.  Keep the
                # shared bootstrap password reproducible while the account is
                # disabled; never overwrite an account that was later enabled.
                if (
                    not options["dry_run"]
                    and not user.is_active
                    and user.access_status == User.AccessStatus.DISABLED
                    and user.block_reason.startswith("Cuenta histórica de trazabilidad")
                ):
                    user.set_password(account_password)
                    user.save(update_fields=["password"])
                    passwords_updated += 1
                continue
            created += 1
            if not options["dry_run"]:
                first_name, *last_name = name.replace("Ing.", "").strip().split()
                user = User(
                    email=email,
                    first_name=first_name,
                    last_name=" ".join(last_name),
                    role=User.Role.LABORATORISTA,
                    is_active=False,
                    email_verified=False,
                    access_status=User.AccessStatus.DISABLED,
                    is_read_only=True,
                    block_reason="Cuenta histórica de trazabilidad. Sin acceso hasta validación administrativa.",
                )
                user.set_password(account_password)
                user.save()

        self.stdout.write(json.dumps({
            "mode": "dry_run" if options["dry_run"] else "apply",
            "reportes_actualizados": report_updates,
            "responsables_historicos": len(names),
            "cuentas_creadas_inactivas": created,
            "cuentas_historicas_existentes": existing,
            "contrasenas_historicas_actualizadas": passwords_updated,
        }, ensure_ascii=False))

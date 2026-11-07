"""Load approved source master data into an empty local Global Oil baseline."""

import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.activesTree.api.models.index import Lubricante
from apps.activesTree.api.models.index import PuntoMuestreo
from apps.activesTree.api.models.machines.index import Maquina
from apps.misc.api.models.companies.index import Empresa
from apps.misc.api.models.dynamicTechnicalConfig.index import (
    CampoTecnicoMuestra,
    CatalogoTecnico,
    CatalogoTecnicoItem,
    CatalogoTecnicoVersion,
)
from apps.misc.api.models.pruebas.index import Prueba
from apps.users.api.models.index import User


def token(value):
    return slugify(str(value or "")).replace("-", "_") or "sin_valor"


def normalized_label(value):
    return re.sub(r"\s*-\s*", "-", " ".join(str(value or "").split()))


def unique_token(value, used, limit=30):
    base = token(value)[:limit]
    result = base
    index = 2
    while result in used:
        suffix = f"_{index}"
        result = f"{base[:limit - len(suffix)]}{suffix}"
        index += 1
    used.add(result)
    return result


def read_raw(path):
    with path.open(encoding="utf-8") as source:
        return [json.loads(line)["data"] for line in source if line.strip()]


class Command(BaseCommand):
    help = (
        "Crea maestros históricos a partir de artefactos ETL. "
        "No carga muestras, mediciones ni resultados."
    )

    def add_arguments(self, parser):
        parser.add_argument("--artifacts", default="outputs/migracion_historica_global_oil")
        parser.add_argument("--actor", default="admin@globaloil.local")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--yes", action="store_true")

    def handle(self, *args, **options):
        artifact_root = Path(options["artifacts"])
        raw_path = artifact_root / "staging" / "reportes_oa_raw.jsonl"
        measurement_path = artifact_root / "staging" / "mediciones.csv"
        if not raw_path.is_file() or not measurement_path.is_file():
            raise CommandError("No se encontraron los artefactos ETL de staging. Ejecute primero la extracción.")
        actor = User.objects.filter(email=options["actor"], is_active=True).first()
        if not actor:
            raise CommandError(f"No existe un actor activo: {options['actor']}")
        rows = read_raw(raw_path)
        source_companies = sorted({str(row.get("CLIENTE") or "").strip() for row in rows if row.get("CLIENTE")}, key=str.casefold)
        source_machines = sorted({(str(row.get("CLIENTE") or "").strip(), str(row.get("EQUIPO") or "").strip()) for row in rows if row.get("CLIENTE") and row.get("EQUIPO")}, key=lambda item: (item[0].casefold(), item[1].casefold()))
        lubricant_variants = defaultdict(set)
        for row in rows:
            raw_value = str(row.get("LUBRICANTE") or "").strip()
            if raw_value:
                lubricant_variants[normalized_label(raw_value).casefold()].add(raw_value)
        source_lubricants = [
            min(values, key=lambda item: (normalized_label(item).casefold(), normalized_label(item)))
            for _, values in sorted(lubricant_variants.items())
        ]
        source_catalogs = {
            "tipo_sistema_historico": ("Tipo de sistema histórico", "Tipo", "tipo_sistema_historico"),
            "grado_viscosidad": ("Grado de viscosidad", "Viscosidad", "grado_viscosidad"),
            "especificacion_calidad": ("Especificación de calidad", "Esp_Cal", "especificacion_calidad"),
        }
        source_tests = []
        with measurement_path.open(encoding="utf-8-sig", newline="") as source:
            source_tests = sorted({row["source_column"] for row in csv.DictReader(source)}, key=str.casefold)
        plan = {
            "empresas": len(source_companies),
            "maquinas": len(source_machines),
            "lubricantes": len(source_lubricants),
            "catalogos": len(source_catalogs),
            "pruebas": len(source_tests),
        }
        self.stdout.write(json.dumps(plan, ensure_ascii=False))
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Simulación: no se creó ningún maestro."))
            return
        if not options["yes"]:
            raise CommandError("Operación de escritura. Revise --dry-run y confirme con --yes.")

        audit_rows = []
        with transaction.atomic():
            companies = {}
            for name in source_companies:
                company, created = Empresa.objects.get_or_create(
                    nombre=name,
                    defaults={"is_active": True, "is_internal": False, "status": Empresa.Status.ACTIVE},
                )
                companies[name] = company
                audit_rows.append({"entity": "empresa", "source_value": name, "target_id": company.id, "created": created})
            for company_name, machine_name in source_machines:
                company = companies[company_name]
                machine = Maquina.objects.filter(empresa=company, nombre=machine_name).order_by("id").first()
                created = machine is None
                if created:
                    machine = Maquina.objects.create(nombre=machine_name, codigo_equipo=machine_name, empresa=company, activo=True)
                audit_rows.append({"entity": "maquina", "source_value": f"{company_name} / {machine_name}", "target_id": machine.id, "created": created})
            for name in source_lubricants:
                canonical_name = normalized_label(name)
                candidates = [
                    item for item in Lubricante.objects.filter(fabricante="HISTORICO_GLOBAL_OIL").order_by("id")
                    if normalized_label(item.referencia).casefold() == canonical_name.casefold()
                ]
                lubricant = next((item for item in candidates if item.referencia == canonical_name), None)
                created = lubricant is None and not candidates
                if lubricant is None:
                    lubricant = candidates[0] if candidates else Lubricante.objects.create(
                        fabricante="HISTORICO_GLOBAL_OIL", referencia=canonical_name, nombre=canonical_name, activo=True,
                    )
                duplicates = [item for item in candidates if item.pk != lubricant.pk]
                for duplicate in duplicates:
                    PuntoMuestreo.objects.filter(lubricante_catalogo=duplicate).update(lubricante_catalogo=lubricant)
                    duplicate.delete()
                if lubricant.nombre != canonical_name or lubricant.referencia != canonical_name:
                    lubricant.nombre = canonical_name
                    lubricant.referencia = canonical_name
                    lubricant.save(update_fields=["nombre", "referencia", "actualizado_en"])
                audit_rows.append({"entity": "lubricante", "source_value": canonical_name, "target_id": lubricant.id, "created": created})
            for catalog_code, (catalog_name, source_column, field_code) in source_catalogs.items():
                catalog, created = CatalogoTecnico.objects.get_or_create(
                    codigo=catalog_code,
                    defaults={"nombre": catalog_name, "tipo_muestra": "aceite", "permite_desconocido": True, "activo": True},
                )
                version = catalog.version_actual
                if not version:
                    version, _ = CatalogoTecnicoVersion.objects.get_or_create(
                        catalogo=catalog, numero=1, defaults={"nombre": "Migración histórica", "activo": True},
                    )
                    catalog.version_actual = version
                    catalog.save(update_fields=["version_actual", "updated_at"])
                CampoTecnicoMuestra.objects.get_or_create(
                    tipo_muestra="aceite", codigo=field_code,
                    defaults={"nombre_visible": catalog_name, "catalogo": catalog, "permite_desconocido": True, "activo": True},
                )
                for value in sorted({str(row.get(source_column) or "").strip() for row in rows if row.get(source_column)}, key=str.casefold):
                    item, item_created = CatalogoTecnicoItem.objects.get_or_create(
                        version=version, codigo=token(value)[:120], defaults={"catalogo": catalog, "nombre": value, "activo": True},
                    )
                    audit_rows.append({"entity": "catalogo_item", "source_value": f"{catalog_code}: {value}", "target_id": item.id, "created": item_created})
                audit_rows.append({"entity": "catalogo", "source_value": catalog_code, "target_id": catalog.id, "created": created})
            used_acronyms = set(Prueba.objects.values_list("acronimo", flat=True))
            for source_column in source_tests:
                existing = Prueba.objects.filter(nombre_variable=source_column).order_by("id").first()
                created = existing is None
                if created:
                    existing = Prueba.objects.create(
                        nombre_variable=source_column,
                        acronimo=unique_token(source_column, used_acronyms),
                        unidad_medida="",
                        activo=True,
                    )
                audit_rows.append({"entity": "prueba", "source_value": source_column, "target_id": existing.id, "created": created})

        report_path = artifact_root / "reports" / "carga_maestros.json"
        report_path.write_text(json.dumps({"actor": actor.email, "plan": plan, "created": sum(1 for item in audit_rows if item["created"]), "records": audit_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Maestros cargados. Auditoría: {report_path}"))

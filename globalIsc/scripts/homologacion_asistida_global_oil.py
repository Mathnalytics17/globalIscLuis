#!/usr/bin/env python3
"""Generate read-only matching proposals against the local Django catalog.

It never calls save(), create(), update(), delete(), or migrations.  The CSV
files it emits are evidence for a human approval, not an automatic decision.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")
import django  # noqa: E402

django.setup()

from apps.activesTree.api.models.index import Lubricante  # noqa: E402
from apps.activesTree.api.models.machines.index import Maquina  # noqa: E402
from apps.misc.api.models.companies.index import Empresa  # noqa: E402
from apps.misc.api.models.dynamicTechnicalConfig.index import CatalogoTecnicoItem  # noqa: E402
from apps.misc.api.models.pruebas.index import Prueba  # noqa: E402


def key(value: Any) -> str:
    text = " ".join(str(value or "").split())
    return re.sub(r"\s*-\s*", "-", text).casefold()


def write_csv(path: Path, rows: list[dict[str, Any]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as target:
        writer = csv.DictWriter(target, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_raw(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        return [json.loads(line)["data"] for line in source if line.strip()]


def candidate(row_id: Any = "", label: str = "", match: str = "SIN_COINCIDENCIA", notes: str = "") -> dict[str, str]:
    return {
        "candidate_id": str(row_id or ""),
        "candidate_label": label or "",
        "match_type": match,
        "status": "PENDIENTE_REVISION",
        "decision": "",
        "notes": notes,
    }


def build_proposals(rows: list[dict[str, Any]], destination: Path) -> dict[str, int]:
    companies = list(Empresa.objects.order_by("id").values("id", "nombre"))
    company_by_name = defaultdict(list)
    for item in companies:
        company_by_name[key(item["nombre"])].append(item)

    company_rows = []
    source_companies = sorted({str(row.get("CLIENTE") or "").strip() for row in rows if row.get("CLIENTE")}, key=str.casefold)
    approved_company_candidate: dict[str, int] = {}
    for source_value in source_companies:
        matches = company_by_name[key(source_value)]
        if len(matches) == 1:
            proposal = candidate(matches[0]["id"], matches[0]["nombre"], "COINCIDENCIA_EXACTA")
            approved_company_candidate[key(source_value)] = matches[0]["id"]
        elif len(matches) > 1:
            proposal = candidate(match="AMBIGUA", notes=f"{len(matches)} empresas con el mismo nombre normalizado.")
        else:
            proposal = candidate(notes="No existe coincidencia exacta en Empresa local.")
        company_rows.append({"source_value": source_value, **proposal})
    write_csv(destination / "empresas.csv", company_rows, ["source_value", "candidate_id", "candidate_label", "match_type", "status", "decision", "notes"])

    machines_by_company = defaultdict(list)
    for machine in Maquina.objects.select_related("empresa").order_by("id"):
        machines_by_company[machine.empresa_id].append(machine)
    contexts = sorted({(str(row.get("CLIENTE") or "").strip(), str(row.get("EQUIPO") or "").strip()) for row in rows if row.get("EQUIPO")}, key=lambda value: (value[0].casefold(), value[1].casefold()))
    machine_rows = []
    for source_company, source_machine in contexts:
        company_id = approved_company_candidate.get(key(source_company))
        if not company_id:
            proposal = candidate(match="BLOQUEADA_POR_EMPRESA", notes="La empresa origen no tiene coincidencia exacta aprobable.")
        else:
            matches = [machine for machine in machines_by_company[company_id] if key(machine.nombre) == key(source_machine) or key(machine.codigo_equipo) == key(source_machine)]
            if len(matches) == 1:
                proposal = candidate(matches[0].id, matches[0].nombre, "COINCIDENCIA_EXACTA")
            elif len(matches) > 1:
                proposal = candidate(match="AMBIGUA", notes="Coinciden varios equipos locales para la empresa candidata.")
            else:
                proposal = candidate(notes="No existe coincidencia exacta de nombre o código para la empresa candidata.")
        machine_rows.append({"source_empresa": source_company, "source_equipo": source_machine, **proposal})
    write_csv(destination / "maquinas.csv", machine_rows, ["source_empresa", "source_equipo", "candidate_id", "candidate_label", "match_type", "status", "decision", "notes"])

    lubricants = list(Lubricante.objects.order_by("id").values("id", "nombre", "referencia"))
    lubricant_rows = []
    for source_value in sorted({str(row.get("LUBRICANTE") or "").strip() for row in rows if row.get("LUBRICANTE")}, key=str.casefold):
        matches = [item for item in lubricants if key(item["nombre"]) == key(source_value) or key(item["referencia"]) == key(source_value)]
        if len(matches) == 1:
            proposal = candidate(matches[0]["id"], matches[0]["nombre"], "COINCIDENCIA_EXACTA")
        elif len(matches) > 1:
            proposal = candidate(match="AMBIGUA", notes="Más de un lubricante local coincide por nombre o referencia.")
        else:
            proposal = candidate(notes="No existe coincidencia exacta en Lubricante local.")
        lubricant_rows.append({"source_value": source_value, **proposal})
    write_csv(destination / "lubricantes.csv", lubricant_rows, ["source_value", "candidate_id", "candidate_label", "match_type", "status", "decision", "notes"])

    catalog_items = list(CatalogoTecnicoItem.objects.select_related("catalogo").filter(activo=True).order_by("id"))
    for source_column, source_name in (("Viscosidad", "viscosidades"), ("Tipo", "tipos_sistema"), ("Esp_Cal", "especificaciones")):
        proposal_rows = []
        values = sorted({str(row.get(source_column) or "").strip() for row in rows if row.get(source_column)}, key=str.casefold)
        for source_value in values:
            matches = [item for item in catalog_items if key(item.nombre) == key(source_value)]
            if len(matches) == 1:
                proposal = candidate(matches[0].id, f"{matches[0].catalogo.codigo}: {matches[0].nombre}", "COINCIDENCIA_EXACTA")
            elif len(matches) > 1:
                proposal = candidate(match="AMBIGUA", notes="El valor existe en más de un catálogo técnico.")
            else:
                proposal = candidate(notes="No existe ítem técnico local con coincidencia exacta.")
            proposal_rows.append({"source_value": source_value, **proposal})
        write_csv(destination / f"{source_name}.csv", proposal_rows, ["source_value", "candidate_id", "candidate_label", "match_type", "status", "decision", "notes"])

    test_rows = []
    measurements_path = destination.parent.parent / "staging" / "mediciones.csv"
    with measurements_path.open(encoding="utf-8-sig", newline="") as source:
        source_columns = sorted({item["source_column"] for item in csv.DictReader(source)}, key=str.casefold)
    tests = list(Prueba.objects.order_by("id").values("id", "acronimo", "nombre_variable"))
    for source_column in source_columns:
        matches = [item for item in tests if key(item["acronimo"]) == key(source_column) or key(item["nombre_variable"]) == key(source_column)]
        if len(matches) == 1:
            proposal = candidate(matches[0]["id"], f"{matches[0]['acronimo']}: {matches[0]['nombre_variable']}", "COINCIDENCIA_EXACTA")
        elif len(matches) > 1:
            proposal = candidate(match="AMBIGUA", notes="Coinciden varias pruebas locales.")
        else:
            proposal = candidate(notes="No existe prueba local con coincidencia exacta.")
        test_rows.append({"source_column": source_column, **proposal})
    write_csv(destination / "pruebas.csv", test_rows, ["source_column", "candidate_id", "candidate_label", "match_type", "status", "decision", "notes"])
    return {"empresas": len(company_rows), "maquinas": len(machine_rows), "lubricantes": len(lubricant_rows), "pruebas": len(test_rows)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera propuestas read-only de homologación contra Django local.")
    parser.add_argument("--artifacts", type=Path, default=Path("outputs/migracion_historica_global_oil"))
    args = parser.parse_args()
    raw = args.artifacts / "staging" / "reportes_oa_raw.jsonl"
    if not raw.is_file():
        parser.error(f"No existe el staging generado por la ETL: {raw}")
    destination = args.artifacts / "homologacion" / "propuestas_db_local"
    counts = build_proposals(read_raw(raw), destination)
    (args.artifacts / "reports" / "homologacion_asistida.json").write_text(json.dumps(counts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

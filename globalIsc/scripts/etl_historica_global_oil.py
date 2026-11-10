#!/usr/bin/env python3
"""ETL reproducible (extract + transform + homologation queue) for Global Oil.

This command is intentionally database-free. It reads the two Excel sources and
creates auditable physical artifacts; no Django model is created or modified.
The next ETL phase may consume only approved rows from ``homologacion/``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

from openpyxl import load_workbook


# Both are official exports of the same OA register.  The source changed its
# tab name in later deliveries; the row/column contract stays identical.
REPORT_SHEETS = ("Reporte OA", "Dump OA")
RAW_MEASUREMENT_FIRST = "APARIENCIA"
RAW_MEASUREMENT_LAST = "Zn"
MASTER_COLUMNS = {
    "empresa": "CLIENTE",
    "maquina": "EQUIPO",
    "placa": "PLACA",
    "lubricante": "LUBRICANTE",
    "tipo_sistema": "Tipo",
    "grado_viscosidad": "Viscosidad",
    "especificacion": "Esp_Cal",
    "responsable": "Responsable",
}
SAMPLE_COLUMNS = (
    "OA", "FECHA", "FECHA TOMA DE MUESTRA", "CLIENTE", "CONTACTO", "EQUIPO", "PLACA",
    "LUBRICANTE", "PERIODO DE SERVICIO", "UNIDAD PERIODO DE SERVICIO", "PERIODO EQUIPO",
    "UNIDAD PERIODO EQUIPO", "Tipo", "Viscosidad", "Esp_Cal", "Responsable", "INPUT", "Limit",
    "Observacion",
)
FUTURE_DATE_CUTOFF = date.today()
MINEROS_ALUVIAL_CANONICAL = "MINEROS ALUVIAL S.A.S."


def client_identity(value: Any) -> str:
    """Compare company names without legal-format punctuation or casing noise."""
    # ``S.A.S.`` and ``SAS`` are the same legal suffix.  Removing separators
    # avoids treating ``MINEROS ALUVIAL S.A.S.`` and ``MINEROS ALUVIAL SAS``
    # as different clients during a scoped historical import.
    return re.sub(r"[^A-Z0-9]+", "", value_as_text(value).upper())


def apply_client_scope(rows: list[dict[str, Any]], scope: str) -> list[dict[str, Any]]:
    """Keep the requested client set and collapse known Mineros Aluvial aliases."""
    if scope == "all":
        return rows
    accepted = {"MINEROSALUVIALSAS", "MINEROSALUVIALSASBIC"}
    selected = []
    for row in rows:
        if client_identity(row.get("CLIENTE")) not in accepted:
            continue
        row = dict(row)
        row["CLIENTE"] = MINEROS_ALUVIAL_CANONICAL
        selected.append(row)
    if not selected:
        raise ValueError("No se encontraron registros de Mineros Aluvial S.A.S. o Mineros Aluvial S.A.S. BIC en el Excel.")
    return selected


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def value_as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    # Some workbooks expose formula/helper objects that are not JSON serializable.
    # The raw layer preserves their displayed text instead of serializing internals.
    return value_as_text(value)


def safe_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized or "sin_nombre"


def write_csv(path: Path, rows: Iterable[dict[str, Any]], headers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as target:
        writer = csv.DictWriter(target, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: value_as_text(row.get(key)) for key in headers})


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False, default=json_value) + "\n")


def header_index(headers: list[str], expected: str) -> int:
    expected_key = expected.casefold().strip()
    for index, header in enumerate(headers):
        if header.casefold().strip() == expected_key:
            return index
    raise ValueError(f"No se encontró la columna requerida: {expected!r}")


def parsed_measurement(value: Any) -> tuple[str, str, str]:
    """Return original text, comparator, and numeric portion without changing meaning."""
    text = value_as_text(value)
    matched = re.fullmatch(r"\s*(<=|>=|<|>)?\s*(-?\d+(?:[.,]\d+)?)\s*", text)
    if not matched:
        return text, "", ""
    comparator = matched.group(1) or "="
    return text, comparator, matched.group(2).replace(",", ".")


def normalized_label(value: str) -> str:
    return " ".join(value.split()).upper()


def load_report_rows(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    # The source has a helper formula.  The ETL consumes displayed source values,
    # never formulas, so cached values avoid formula translation/cycle handling.
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet_name = next((name for name in REPORT_SHEETS if name in workbook.sheetnames), None)
    if sheet_name is None:
        allowed = ", ".join(repr(name) for name in REPORT_SHEETS)
        raise ValueError(f"No existe una hoja OA compatible ({allowed}) en {path.name}")
    sheet = workbook[sheet_name]
    headers = [value_as_text(cell.value) for cell in next(sheet.iter_rows(min_row=2, max_row=2))]
    if len(headers) != len(set(headers)):
        duplicates = [name for name, count in Counter(headers).items() if count > 1]
        raise ValueError(f"Encabezados duplicados no soportados: {duplicates}")
    header_index(headers, "OA")
    for column in MASTER_COLUMNS.values():
        header_index(headers, column)
    rows: list[dict[str, Any]] = []
    for source_row, values in enumerate(sheet.iter_rows(min_row=3, values_only=True), start=3):
        record = {header: json_value(value) for header, value in zip(headers, values)}
        if not value_as_text(record.get("OA")):
            continue
        record["_source_row"] = source_row
        rows.append(record)
    workbook.close()
    return headers, rows


def extract_knowledge(path: Path, destination: Path) -> dict[str, int]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    counts: dict[str, int] = {}
    for name in workbook.sheetnames:
        sheet = workbook[name]
        rows = [[json_value(cell.value) for cell in row] for row in sheet.iter_rows()]
        while rows and not any(value_as_text(value) for value in rows[-1]):
            rows.pop()
        width = max((len(row) for row in rows), default=0)
        output_rows = []
        for row_number, row in enumerate(rows, start=1):
            output_rows.append({"source_row": row_number, **{f"col_{index + 1}": value for index, value in enumerate(row)}})
        headers = ["source_row"] + [f"col_{index + 1}" for index in range(width)]
        write_csv(destination / f"{safe_name(name)}.csv", output_rows, headers)
        counts[name] = len(output_rows)
    workbook.close()
    return counts


def create_homologation(rows: list[dict[str, Any]], headers: list[str], destination: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entity, column in MASTER_COLUMNS.items():
        values = sorted({value_as_text(row[column]) for row in rows if value_as_text(row[column])}, key=str.casefold)
        output = [{
            "entity_type": entity,
            "source_value": value,
            "normalized_value": normalized_label(value),
            "proposed_destination": "",
            "status": "PENDIENTE",
            "decision": "",
            "notes": "",
        } for value in values]
        write_csv(destination / f"{entity}.csv", output, [
            "entity_type", "source_value", "normalized_value", "proposed_destination", "status", "decision", "notes",
        ])
        counts[entity] = len(output)

    first = header_index(headers, RAW_MEASUREMENT_FIRST)
    last = header_index(headers, RAW_MEASUREMENT_LAST)
    measurement_rows = []
    for position, source_column in enumerate(headers[first:last + 1], start=1):
        measurement_rows.append({
            "source_column": source_column,
            "family": "metal" if first + position - 1 >= header_index(headers, "Ag") else "fisico_quimico",
            "proposed_test_acronym": safe_name(source_column).upper()[:30],
            "unit": "",
            "status": "PENDIENTE",
            "decision": "",
            "notes": "Definir unidad, prueba destino y criterio de límite.",
        })
    write_csv(destination / "mediciones.csv", measurement_rows, [
        "source_column", "family", "proposed_test_acronym", "unit", "status", "decision", "notes",
    ])
    counts["mediciones"] = len(measurement_rows)
    return counts


def make_artifacts(report_path: Path, knowledge_path: Path, output: Path, replace: bool, client_scope: str) -> dict[str, Any]:
    if output.exists() and any(output.iterdir()):
        if not replace:
            raise FileExistsError(f"La salida ya existe y no está vacía: {output}. Use --replace para regenerarla.")
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    headers, rows = load_report_rows(report_path)
    source_record_count = len(rows)
    rows = apply_client_scope(rows, client_scope)
    oa_counts = Counter(value_as_text(row["OA"]) for row in rows)
    duplicate_oa = sorted(oa for oa, count in oa_counts.items() if count > 1)
    warnings: list[dict[str, str]] = []
    measurements: list[dict[str, Any]] = []
    samples: list[dict[str, Any]] = []
    interpretations: list[dict[str, Any]] = []
    first = header_index(headers, RAW_MEASUREMENT_FIRST)
    last = header_index(headers, RAW_MEASUREMENT_LAST)
    metal_start = header_index(headers, "Ag")
    comment_columns = [header for header in headers if re.fullmatch(r"COM_\d+", header or "")]

    for row in rows:
        oa = value_as_text(row["OA"])
        for date_column in ("FECHA", "FECHA TOMA DE MUESTRA"):
            raw_date = row.get(date_column)
            if isinstance(raw_date, datetime):
                date_value = raw_date.date()
            elif isinstance(raw_date, date):
                date_value = raw_date
            else:
                date_value = None
            if date_value and date_value > FUTURE_DATE_CUTOFF:
                warnings.append({"oa": oa, "source_row": str(row["_source_row"]), "type": "FECHA_FUTURA", "detail": f"{date_column}: {date_value.isoformat()}"})
        samples.append({
            "oa": oa,
            "source_row": row["_source_row"],
            **{safe_name(column): value_as_text(row.get(column)) for column in SAMPLE_COLUMNS},
        })
        for index in range(first, last + 1):
            source_column = headers[index]
            original, comparator, numeric_value = parsed_measurement(row.get(source_column))
            if not original:
                continue
            measurements.append({
                "oa": oa,
                "source_row": row["_source_row"],
                "family": "metal" if index >= metal_start else "fisico_quimico",
                "source_column": source_column,
                "original_value": original,
                "comparator": comparator,
                "numeric_value": numeric_value,
                "unit": "",
            })
        interpretations.append({
            "oa": oa,
            "source_row": row["_source_row"],
            "conclusion": value_as_text(row.get("CONCLUSIÓN")),
            "comments": {column: value_as_text(row.get(column)) for column in comment_columns if value_as_text(row.get(column))},
        })

    raw_rows = [{"source_row": row["_source_row"], "data": {key: value for key, value in row.items() if key != "_source_row"}} for row in rows]
    write_jsonl(output / "staging" / "reportes_oa_raw.jsonl", raw_rows)
    write_csv(output / "staging" / "muestras.csv", samples, ["oa", "source_row"] + [safe_name(column) for column in SAMPLE_COLUMNS])
    write_csv(output / "staging" / "mediciones.csv", measurements, ["oa", "source_row", "family", "source_column", "original_value", "comparator", "numeric_value", "unit"])
    write_jsonl(output / "staging" / "interpretaciones.jsonl", interpretations)
    write_csv(output / "qa" / "duplicados_oa.csv", [{"oa": oa, "occurrences": oa_counts[oa]} for oa in duplicate_oa], ["oa", "occurrences"])
    write_csv(output / "qa" / "advertencias.csv", warnings, ["oa", "source_row", "type", "detail"])
    homologation_counts = create_homologation(rows, headers, output / "homologacion")
    knowledge_counts = extract_knowledge(knowledge_path, output / "catalogos_fuente")

    manifest = {
        "etl": "global_oil_historica",
        "generated_at": datetime.now().astimezone().isoformat(),
        "mode": "extract_transform_homologation_only",
        "client_scope": client_scope,
        "client_aliases_collapsed": {"MINEROS ALUVIAL SAS BIC": MINEROS_ALUVIAL_CANONICAL} if client_scope == "mineros" else {},
        "database_written": False,
        "sources": {
            "reportes": {"path": str(report_path.resolve()), "sha256": sha256(report_path)},
            "conocimiento": {"path": str(knowledge_path.resolve()), "sha256": sha256(knowledge_path)},
        },
        "controls": {
            "source_records": source_record_count,
            "records": len(rows),
            "unique_oa": len(oa_counts),
            "duplicate_oa": len(duplicate_oa),
            "measurements": len(measurements),
            "warnings": len(warnings),
            "homologation": homologation_counts,
            "knowledge_rows": knowledge_counts,
        },
    }
    (output / "reports").mkdir(exist_ok=True)
    (output / "reports" / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report = [
        "# Reporte de extracción ETL Global Oil",
        "",
        "Esta ejecución solo extrajo, normalizó y dejó colas de homologación. No escribió en Django ni en PostgreSQL.",
        "",
        "## Controles",
        "",
        f"- Registros OA: {len(rows)}",
        f"- OA únicos: {len(oa_counts)}",
        f"- OA duplicados: {len(duplicate_oa)}",
        f"- Mediciones normalizadas: {len(measurements)}",
        f"- Advertencias: {len(warnings)}",
        "",
        "## Siguiente revisión humana",
        "",
        "1. Completar los CSV de `homologacion/` con destino, estado y decisión.",
        "2. Resolver cada advertencia en `qa/advertencias.csv`.",
        "3. Aprobar el manifiesto y solo entonces ejecutar una futura fase de aplicación a Django.",
    ]
    (output / "reports" / "reporte_ejecucion.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Extrae y prepara la migración histórica Global Oil sin tocar la base de datos.")
    parser.add_argument("--reportes", type=Path, required=True, help="Excel histórico: REPORTES ...xlsx")
    parser.add_argument("--conocimiento", type=Path, required=True, help="Excel técnico: Base_Conocimiento ...xlsx")
    parser.add_argument("--output", type=Path, required=True, help="Directorio de artefactos físicos")
    parser.add_argument("--replace", action="store_true", help="Reemplaza completamente el directorio de salida indicado")
    parser.add_argument("--client-scope", choices=("all", "mineros"), default="all", help="all carga todos los clientes; mineros conserva y unifica solo Mineros Aluvial S.A.S. y su variante BIC.")
    args = parser.parse_args()
    for source in (args.reportes, args.conocimiento):
        if not source.is_file():
            parser.error(f"No existe el archivo fuente: {source}")
    try:
        manifest = make_artifacts(args.reportes, args.conocimiento, args.output, args.replace, args.client_scope)
    except (ValueError, FileExistsError) as error:
        parser.error(str(error))
    print(json.dumps(manifest["controls"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

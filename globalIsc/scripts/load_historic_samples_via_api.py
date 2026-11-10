#!/usr/bin/env python3
"""Create historical batches and samples through the public local API only.

Each original OA remains in ``campos_adicionales.oa_origen`` and the generated
report maps that OA to the platform sample ID.  Batches are deliberately
grouped by company/month and capped at 50 samples so they remain usable in the
normal reception and laboratory workflow.
"""
import argparse
import csv
import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

from etl_global_oil_domain import has_source_plate, norm, plate_code, split_machine_and_point
from load_global_oil_via_api import Api


def rows(path):
    source = []
    for line in path.open(encoding="utf-8"):
        if not line.strip():
            continue
        record = json.loads(line)
        row = dict(record["data"])
        # This is provenance, not a fabricated timestamp.  It resolves only
        # equal sampling dates in the historical trend view.
        row["_orden_migracion_origen"] = record.get("source_order", record.get("source_row"))
        row["_source_id"] = record.get("source_id")
        source.append(row)
    return source


def as_date(value):
    """Normalize ISO, common text and Excel serial dates without inventing today."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    if not text or text == "00:00:00":
        return None
    if len(text) >= 10 and text[:4].isdigit():
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            pass
    try:
        serial = float(text.replace(",", "."))
        if 1 <= serial <= 60000:
            return (date(1899, 12, 30) + timedelta(days=int(serial))).isoformat()
    except ValueError:
        pass
    for pattern in ("%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def sample_date(row):
    for column in ("FECHA TOMA DE MUESTRA", "FECHA"):
        normalized = as_date(row.get(column))
        if normalized:
            return normalized
    raise ValueError(f"OA {row.get('OA')}: fecha de toma/reporte inválida")


def sample_validation_errors(row):
    """Return source-data reasons that prevent a person-like sample intake."""
    errors = []
    try:
        sample_date(row)
    except ValueError:
        errors.append("Sin fecha de toma ni fecha de reporte válida")
    if not norm(row.get("CLIENTE")):
        errors.append("Sin cliente")
    if not norm(row.get("EQUIPO")):
        errors.append("Sin equipo")
    return errors


def number(value):
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None


def unit(value):
    key = norm(value).casefold()
    return {"hora": "horas", "horas": "horas", "hr": "horas", "km": "km", "kilometros": "km", "kilómetros": "km", "millas": "millas", "dias": "dias", "días": "dias"}.get(key)


def sample_payload(row, point_id, atributos_tecnicos):
    lubricant = norm(row.get("LUBRICANTE"))
    equipment = norm(row.get("EQUIPO"))
    oil_service = number(row.get("PERIODO DE SERVICIO"))
    equipment_service = number(row.get("PERIODO DE SERVICIO EQUIPO"))
    return {
        "fecha_toma": sample_date(row),
        "tipo_muestra": "aceite", "condicion": "usada",
        "contacto_cliente": norm(row.get("CONTACTO")) or None,
        "equipo_placa": norm(row.get("PLACA")) if equipment == "DESCONOCIDO" else None,
        "punto_muestreo": point_id,
        "lubricante_nuevo": lubricant or None,
        "referencia_marca": lubricant or None,
        "periodo_servicio_aceite": oil_service,
        "unidad_periodo_aceite": unit(row.get("PERIODO DE SERVICIO UNIDAD")),
        "periodo_servicio_equipo": equipment_service,
        "unidad_periodo_equipo": unit(row.get("UNIDAD PERIODO DE SERVICIO EQUIPO")),
        "observaciones": norm(row.get("Observacion")) or None,
        "atributos_tecnicos": atributos_tecnicos,
        "campos_adicionales": {
            # OA is namespaced by source workbook in the ETL because several
            # yearly exports reuse the same laboratory OA numbering.
            "oa_origen": str(row.get("OA") or "").strip(),
            "oa_original": str(row.get("OA_ORIGINAL") or row.get("OA") or "").strip(),
            "archivo_origen": str(row.get("_source_id") or "").strip(),
            "orden_migracion_origen": row.get("_orden_migracion_origen"),
            "fecha_reporte_origen": as_date(row.get("FECHA")),
            "tipo_sistema_origen": norm(row.get("Tipo")),
            "grado_viscosidad_origen": norm(row.get("Viscosidad")),
            "especificacion_origen": norm(row.get("Esp_Cal")),
            "conclusion_origen": norm(row.get("CONCLUSIÓN")),
        },
    }


def sample_attributes(api, row):
    """Resolve only exact source-backed technical criteria for a sample."""
    if not hasattr(api, "_technical_attribute_maps"):
        fields = {item.get("codigo"): item for item in api.get("technical-config/sample-fields/", {"page_size": 100})}
        catalogs = {item.get("codigo"): item for item in api.get("technical-config/catalogs/", {"page_size": 100})}
        api._technical_attribute_maps = (fields, {
            code: {norm(item.get("nombre")): item for item in catalog.get("items", [])}
            for code, catalog in catalogs.items()
        })
    fields, items_by_catalog = api._technical_attribute_maps
    source = (
        ("tipo_sistema_uso", "tipo_sistema_uso", row.get("Tipo")),
        ("grado_viscosidad", "grado_viscosidad", row.get("Viscosidad")),
        ("nivel_desempeno", "nivel_desempeno", row.get("Esp_Cal")),
    )
    attributes = []
    for field_code, catalog_code, value in source:
        field = fields.get(field_code)
        item = items_by_catalog.get(catalog_code, {}).get(norm(value))
        if field and item and norm(value) not in {"", "0", "-", "DESCONOCIDO"}:
            attributes.append({"campo_tecnico": field["id"], "catalogo": item["catalogo"], "item": item["id"], "desconocido": False})
    return attributes


def chunks(items, size=50):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def main():
    parser = argparse.ArgumentParser(description="Carga muestras históricas mediante la API local.")
    parser.add_argument("--artifacts", type=Path, default=Path("outputs/migracion_historica_global_oil"))
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email"); parser.add_argument("--password"); parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    source = rows(args.artifacts / "staging" / "reportes_oa_raw.jsonl")
    point_rows = list(csv.DictReader((args.artifacts / "homologacion" / "puntos_medicion.csv").open(encoding="utf-8-sig")))
    point_specs = {}
    for item in point_rows:
        point_spec = {
            "codigo": norm(item["codigo_punto"]),
            "estado": item["estado"],
            "nombre": norm(item["nombre_punto"]),
        }
        company = norm(item["empresa_origen"])
        machine = norm(item["maquina_origen"])
        if item["estado"] == "LISTO_PLACA":
            point_specs[(company, machine, "placa", point_spec["codigo"])] = point_spec
        else:
            source_names = [item["nombre_punto"], *(item.get("punto_origen") or "").split("|")]
            for source_name in source_names:
                point_specs[(company, machine, "nombre", norm(source_name))] = point_spec
    rejected = []
    eligible = []
    for row in source:
        errors = sample_validation_errors(row)
        if errors:
            rejected.append({"oa": str(row.get("OA") or "").strip(), "motivos": errors})
        else:
            eligible.append(row)
    groups = defaultdict(list)
    for row in eligible:
        company = norm(row.get("CLIENTE"))
        groups[(company, sample_date(row)[:7])].append(row)
    batch_count = sum(len(list(chunks(group))) for group in groups.values())
    summary = {"mode": "dry_run", "oa_fuente": len(source), "oa_importables": len(eligible), "oa_omitidas": len(rejected), "company_month_groups": len(groups), "batches": batch_count, "writes": False}
    if not args.apply:
        print(json.dumps(summary, ensure_ascii=False)); return
    if not args.email or not args.password:
        parser.error("--email y --password son obligatorios con --apply")
    api = Api(args.base_url, args.email, args.password)
    # The OA is the immutable external business key.  Query it through the
    # API before creating a batch so a rerun imports only genuinely new rows.
    existing = {}
    for row in eligible:
        oa = str(row.get("OA") or "").strip()
        matches = api.get("lubrication/samples/", {"oa_origen": oa})
        if len(matches) > 1:
            raise RuntimeError(f"OA {oa}: la API devolvió {len(matches)} muestras; corrija el duplicado antes de reintentar.")
        if matches:
            existing[oa] = {"oa": oa, "muestra": matches[0]["id"], "lote": matches[0].get("lote")}
    new_source = [row for row in eligible if str(row.get("OA") or "").strip() not in existing]
    groups = defaultdict(list)
    for row in new_source:
        company = norm(row.get("CLIENTE"))
        groups[(company, sample_date(row)[:7])].append(row)
    company_cache, machine_cache, point_cache, audit = {}, {}, {}, list(existing.values())

    def point_for(row):
        company = norm(row.get("CLIENTE")); machine, point = split_machine_and_point(norm(row.get("EQUIPO")))
        company_id = company_cache.get(company)
        if company_id is None:
            matches = [item for item in api.get("companies/buscar/", {"nombre": company}) if norm(item.get("nombre")) == company]
            if not matches: raise RuntimeError(f"Empresa inexistente en API: {company}")
            company_id = company_cache[company] = matches[0]["id"]
        machine_key = (company, machine)
        machine_id = machine_cache.get(machine_key)
        if machine_id is None:
            matches = [item for item in api.get("machines/", {"empresa": company_id, "search": machine}) if norm(item.get("nombre")) == machine]
            if not matches: raise RuntimeError(f"Máquina inexistente en API: {company} / {machine}")
            machine_id = machine_cache[machine_key] = matches[0]["id"]
        source_plate = plate_code(row.get("PLACA"))
        identity = (company, machine, "placa", source_plate) if has_source_plate(source_plate) else (company, machine, "nombre", point)
        point_spec = point_specs.get(identity)
        if not point_spec:
            raise RuntimeError(f"Punto no homologado en artefactos: {company} / {machine} / {point}")
        code, sourced_by_plate = point_spec["codigo"], point_spec["estado"] == "LISTO_PLACA"
        point_key = (machine_id, "placa", code) if sourced_by_plate else (machine_id, "nombre", point, code)
        point_id = point_cache.get(point_key)
        if point_id is None:
            # Do not assume the first API page contains the requested point:
            # dredges commonly have more than the default 20 points.
            machine_points = api.get("sampling-points/", {"machine": machine_id, "page_size": 1000})
            matches = [item for item in machine_points if norm(item.get("codigo")) == code] if sourced_by_plate else [item for item in machine_points if (
                norm(item.get("nombre")) == point_spec["nombre"] and norm(item.get("codigo")) == code
            )]
            if not matches:
                available = [(norm(item.get("nombre")), norm(item.get("codigo"))) for item in machine_points]
                raise RuntimeError(f"Punto inexistente en API: {company} / {machine} / {point}; código={code!r}; disponibles={available}")
            point_id = point_cache[point_key] = matches[0]["id"]
        return point_id

    for (company, month), group in sorted(groups.items()):
        company_id = None
        for part_number, part in enumerate(chunks(group), 1):
            samples = [sample_payload(row, point_for(row), sample_attributes(api, row)) for row in part]
            batch = api.post("lubrication/sample-batches/", {
                "tipo_cliente": "registrado", "cliente_empresa": company_cache[company],
                "contacto_nombre": norm(part[0].get("CONTACTO")) or None,
                "fecha_envio": sample_date(part[0]),
                "estado": "registrado",
                "observaciones": f"Migración histórica Global Oil: {company}, {month}, bloque {part_number}.",
                "muestras": samples,
            })
            response_samples = batch.get("muestras", [])
            if len(response_samples) != len(part):
                raise RuntimeError(f"Lote {batch.get('id')}: API devolvió {len(response_samples)} de {len(part)} muestras")
            for source_row, created in zip(part, response_samples):
                audit.append({"oa": str(source_row.get("OA")), "muestra": created["id"], "lote": batch["id"]})
    report = args.artifacts / "reports" / "carga_api_muestras.json"
    report.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rejected_report = args.artifacts / "qa" / "muestras_no_importables.json"
    rejected_report.parent.mkdir(parents=True, exist_ok=True)
    rejected_report.write_text(json.dumps(rejected, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary.update({"mode": "apply", "writes": True, "created_samples": len(new_source), "reused_samples": len(existing), "created_batches": sum(len(list(chunks(group))) for group in groups.values()), "rejected_samples": len(rejected), "report": str(report), "rejected_report": str(rejected_report)})
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

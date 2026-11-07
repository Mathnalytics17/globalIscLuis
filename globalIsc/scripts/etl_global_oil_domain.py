#!/usr/bin/env python3
"""Domain transform for Global Oil staging; no database writes."""
import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

BRANDS = (
    (r"\b(?:MAXFLUID|MAXDIESEL|MAXGEAR|GLOBAL\s+(?:GAS|TDH|MAX))\b", "Global Oil"),
    (r"\bCASTROL\b", "Castrol"), (r"\bMOBIL\b", "Mobil"), (r"\bSHELL\b", "Shell"),
    (r"\bCHEVRON\b|\bDELO\b", "Chevron"), (r"\bDISPEL\b|\bDIS\s+ISO\b", "Dispel"),
    (r"\bELF\b", "ELF"), (r"\bENI\b", "Eni"), (r"\bLIQUI\s+MOLY\b", "LIQUI MOLY"),
    (r"\bYAMA(?:HA|LUBE)\b", "Yamalube"), (r"\bZF\b|\bLIFEGUARD\b", "ZF"), (r"\bPETROBRAS\b", "Petrobras"),
)
METALS = ("Ag", "Al", "B", "Ba", "Ca", "Cd", "Cr", "Cu", "Fe", "K", "Li", "Mg", "Mn", "Mo", "Na", "Ni", "P", "Pb", "Sb", "Si", "Sn", "Ti", "V", "Zn")
FOAM = {"Espuma Seq I": ("Secuencia I", "EI", "FI"), "Espuma Seq II": ("Secuencia II", "EII", "FII"), "Espuma Seq III": ("Secuencia III", "EIII", "FIII")}


def norm(value):
    return re.sub(r"\s*-\s*", "-", " ".join(str(value or "").split())).strip()


def normalized_numeric_measurement(value):
    """Return a canonical numeric value, or ``None`` for a non-result.

    Historical OA exports use both ``<1`` and ``-`` for a measurement that
    must not create a result.  The laboratory API only accepts numeric values;
    silently passing either marker would make the import inconsistent with the
    source and fail later in the workflow.
    """
    text = str(value or "").strip()
    if not text or text in {"-", "–", "—"} or re.fullmatch(r"<\s*1(?:[.,]0+)?", text):
        return None
    compact = text.replace(" ", "")
    if "," in compact and "." in compact:
        # Treat the last separator as decimal; this supports 1,234.50 and
        # 1.234,50 without relying on the workstation locale.
        if compact.rfind(",") > compact.rfind("."):
            compact = compact.replace(".", "").replace(",", ".")
        else:
            compact = compact.replace(",", "")
    else:
        compact = compact.replace(",", ".")
    if not re.fullmatch(r"[-+]?(?:\d+(?:\.\d+)?|\.\d+)", compact):
        return None
    return compact


def is_corrupted_measurement_row(row):
    """Detect a legacy export row where measurement cells contain headers.

    Some OA exports preserve the sample identity but shift a repeated header
    into the analytical columns.  Such values are not measurements and must
    never be reinterpreted as metals, foam, or physical test results.
    """
    return norm(row.get("Apariencia")).casefold() == "apariencia" and norm(row.get("Olor")).casefold() == "olor"


def stable_code(*parts):
    text = "|".join(norm(part).casefold() for part in parts)
    return "PM-" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:12].upper()


def split_machine_and_point(equipment):
    """Extract the parent dredge from a legacy equipment/punto description."""
    text = norm(equipment)
    match = re.search(r"\b(DRAGA\s+(?:NO\.?|N[ºO]?\.?|#)?\s*\d+)\b", text, re.I)
    if not match:
        return text, "Punto principal"
    # `DRAGA No.5`, `DRAGA No. 5`, `DRAGA N°5` and `DRAGA #5` are the
    # same physical machine.  Rebuild from the numeric identity, never by
    # formatting the source substring.
    number = re.search(r"\d+", match.group(1)).group(0)
    machine = f"DRAGA No.{int(number)}"
    point = norm((text[:match.start()] + text[match.end():]).strip(" -/|")) or "Punto principal"
    return machine, point


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as target:
        for row in rows:
            target.write(json.dumps(row, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description="Genera homologaciones de dominio desde staging Global Oil.")
    parser.add_argument("--artifacts", type=Path, default=Path("outputs/migracion_historica_global_oil"))
    args = parser.parse_args()
    raw_path = args.artifacts / "staging" / "reportes_oa_raw.jsonl"
    if not raw_path.is_file(): parser.error("No existe staging/reportes_oa_raw.jsonl")
    rows = [json.loads(line)["data"] for line in raw_path.open(encoding="utf-8") if line.strip()]
    points, lubricants = {}, {}
    for row in rows:
        company, equipment, lubricant, system = (norm(row.get(key)) for key in ("CLIENTE", "EQUIPO", "LUBRICANTE", "Tipo"))
        machine, point_name = split_machine_and_point(equipment)
        if company and machine:
            key = (company, machine, point_name)
            point_code = stable_code(*key)
            point = points.setdefault(key, {"empresa_origen": company, "maquina_origen": machine, "punto_origen": point_name, "lubricantes_historicos": set(), "tipos_historicos": set(), "codigo_punto": point_code, "nombre_punto": point_name, "estado": "PENDIENTE_API"})
            if lubricant: point["lubricantes_historicos"].add(lubricant)
            if system: point["tipos_historicos"].add(system)
        if lubricant:
            brand, reference, status = "", lubricant, "PENDIENTE_REVISION"
            for pattern, candidate in BRANDS:
                if re.search(pattern, lubricant, re.I):
                    brand, status = candidate, "CONFIRMADA_POR_REGLA"
                    reference = norm(re.sub(pattern, "", lubricant, flags=re.I)).strip(" -/") or lubricant
                    break
            lubricants[lubricant] = {"origen": lubricant, "marca": brand, "referencia": reference, "estado": status}
    point_rows = []
    for point in points.values():
        point["lubricantes_historicos"] = " | ".join(sorted(point["lubricantes_historicos"], key=str.casefold))
        point["tipos_historicos"] = " | ".join(sorted(point["tipos_historicos"], key=str.casefold))
        point_rows.append(point)
    point_rows.sort(key=lambda item: (item["empresa_origen"].casefold(), item["maquina_origen"].casefold(), item["nombre_punto"].casefold()))
    write_csv(args.artifacts / "homologacion" / "puntos_medicion.csv", point_rows, ["empresa_origen", "maquina_origen", "punto_origen", "lubricantes_historicos", "tipos_historicos", "codigo_punto", "nombre_punto", "estado"])
    lubricant_rows = sorted(lubricants.values(), key=lambda item: item["origen"].casefold())
    write_csv(args.artifacts / "homologacion" / "lubricantes_dominio.csv", lubricant_rows, ["origen", "marca", "referencia", "estado"])
    layout = [{"prueba": "ELEMENTOS", "resultado": metal, "campo": metal, "unidad": "ppm", "origen": metal} for metal in METALS]
    for source, (result, first, second) in FOAM.items():
        layout.extend([{"prueba": "ESPUMA", "resultado": result, "campo": first, "unidad": "mL/mL", "origen": source}, {"prueba": "ESPUMA", "resultado": result, "campo": second, "unidad": "mL/mL", "origen": source}])
    write_csv(args.artifacts / "staging" / "layout_pruebas_compuestas.csv", layout, ["prueba", "resultado", "campo", "unidad", "origen"])
    compound_rows, compound_errors, corrupted_rows, nonnumeric_rows = [], [], [], []
    for row in rows:
        oa = str(row.get("OA") or "").strip()
        if is_corrupted_measurement_row(row):
            corrupted_rows.append({"oa": oa, "reason": "Las columnas analíticas contienen una fila de encabezados repetida."})
            continue
        elements = {}
        for metal in METALS:
            raw_value = row.get(metal)
            numeric_value = normalized_numeric_measurement(raw_value)
            if numeric_value is not None:
                elements[metal] = numeric_value
            elif str(raw_value or "").strip() not in {"", "-", "–", "—"} and not re.fullmatch(r"<\s*1(?:[.,]0+)?", str(raw_value or "").strip()):
                nonnumeric_rows.append({"oa": oa, "source": metal, "value": str(raw_value), "reason": "Valor no numérico omitido; el API exige resultado numérico."})
        foam = {}
        for source, (result, first, second) in FOAM.items():
            value = str(row.get(source) or "").strip()
            if not value:
                continue
            parts = [part.strip() for part in value.split("/")]
            if len(parts) != 2:
                compound_errors.append({"oa": oa, "source": source, "value": value, "reason": "Espuma debe tener formato EI/FI."})
                continue
            parsed_parts = {field: normalized_numeric_measurement(part) for field, part in ((first, parts[0]), (second, parts[1]))}
            for field, parsed in parsed_parts.items():
                if parsed is None and str(parts[0] if field == first else parts[1]).strip() not in {"", "-", "–", "—"}:
                    nonnumeric_rows.append({"oa": oa, "source": source, "value": value, "reason": f"Componente {field} no numérico omitido."})
            parsed_parts = {field: parsed for field, parsed in parsed_parts.items() if parsed is not None}
            if parsed_parts:
                foam[result] = {**parsed_parts, "source_value": value}
        if elements or foam:
            compound_rows.append({"oa": oa, "elements": elements, "foam": foam})
    write_jsonl(args.artifacts / "staging" / "resultados_compuestos.jsonl", compound_rows)
    write_csv(args.artifacts / "qa" / "resultados_compuestos_invalidos.csv", compound_errors, ["oa", "source", "value", "reason"])
    write_csv(args.artifacts / "qa" / "resultados_compuestos_no_numericos.csv", nonnumeric_rows, ["oa", "source", "value", "reason"])
    write_csv(args.artifacts / "qa" / "filas_analiticas_corruptas.csv", corrupted_rows, ["oa", "reason"])
    report = {"records": len(rows), "puntos_medicion": len(point_rows), "lubricantes": len(lubricant_rows), "lubricantes_pendientes": sum(item["estado"] != "CONFIRMADA_POR_REGLA" for item in lubricant_rows), "elementos": len(METALS), "campos_espuma": 6, "muestras_con_resultados_compuestos": len(compound_rows), "errores_compuestos": len(compound_errors), "valores_compuestos_no_numericos": len(nonnumeric_rows), "filas_analiticas_corruptas": len(corrupted_rows)}
    (args.artifacts / "reports" / "dominio_etl.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__": main()

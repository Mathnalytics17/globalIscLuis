#!/usr/bin/env python3
"""Turn source physical fields into API result-entry payloads; no DB writes."""
import argparse
import json
import re
from pathlib import Path

from physical_measurement_schema import PHYSICAL_MEASUREMENTS, COMPOUND_PHYSICAL_MEASUREMENTS


def present(value):
    return value is not None and str(value).strip() not in {"", "-", "N/A", "NA"}


def corrupted_measurement_row(row):
    """Reject a legacy row where the repeated headers displaced results."""
    return str(row.get("Apariencia") or "").strip().casefold() == "apariencia" and str(row.get("Olor") or "").strip().casefold() == "olor"


def main():
    parser = argparse.ArgumentParser(description="Construye cargas API de mediciones físicas.")
    parser.add_argument("--artifacts", type=Path, default=Path("outputs/migracion_historica_global_oil"))
    args = parser.parse_args()
    source = args.artifacts / "staging" / "reportes_oa_raw.jsonl"
    target = args.artifacts / "staging" / "api_result_payloads_physical.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    counts = {definition[1]: 0 for definition in PHYSICAL_MEASUREMENTS}
    counts.update({definition[1]: 0 for definition in COMPOUND_PHYSICAL_MEASUREMENTS})
    total = 0
    iso_incomplete, corrupted_rows = [], []
    with target.open("w", encoding="utf-8") as output:
        for line in source.open(encoding="utf-8"):
            row = json.loads(line)["data"]
            oa = str(row.get("OA") or "").strip()
            if corrupted_measurement_row(row):
                corrupted_rows.append({"oa": oa, "reason": "Las columnas analíticas contienen una fila de encabezados repetida."})
                continue
            for column, code, name, unit, data_type in PHYSICAL_MEASUREMENTS:
                value = row.get(column)
                if not oa or not present(value):
                    continue
                # API result-entry identifies nested fields by their emitted
                # labels.  `code` remains the stable test identity only.
                output.write(json.dumps({"oa": oa, "test_code": code, "values": [{"result_code": name, "component_code": code, "value": str(value), "source_column": column}]}, ensure_ascii=False) + "\n")
                counts[code] += 1; total += 1
            for column, code, name, unit, components in COMPOUND_PHYSICAL_MEASUREMENTS:
                value = row.get(column)
                if not oa or not present(value):
                    continue
                tokens = [token.strip() for token in str(value).split("/")]
                if len(tokens) != 3 or any(token not in {"*", "", "-"} and not re.fullmatch(r"\d{1,2}", token) for token in tokens):
                    iso_incomplete.append({"oa": oa, "source": str(value), "missing_components": list(components), "reason": "Código ISO 4406 inválido; resultado omitido."})
                    continue
                values = [
                    {"result_code": name, "component_code": component, "value": raw, "source_column": column}
                    for component, raw in zip(components, tokens) if re.fullmatch(r"\d{1,2}", raw)
                ]
                if not values:
                    iso_incomplete.append({"oa": oa, "source": str(value), "missing_components": list(components)})
                    continue
                missing = [component for component, raw in zip(components, tokens) if not re.fullmatch(r"\d{1,2}", raw)]
                if missing:
                    iso_incomplete.append({"oa": oa, "source": str(value), "missing_components": missing})
                output.write(json.dumps({"oa": oa, "test_code": code, "values": [
                    *values
                ]}, ensure_ascii=False) + "\n")
                counts[code] += 1; total += len(values)
    report = args.artifacts / "reports" / "payloads_resultados_fisicos.json"
    report.write_text(json.dumps({"payloads": total, "by_test": counts, "iso4406_incompletos": iso_incomplete, "filas_analiticas_corruptas": corrupted_rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"payloads": total, "tests": len(counts), "path": str(target)}, ensure_ascii=False))


if __name__ == "__main__": main()

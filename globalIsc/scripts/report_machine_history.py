#!/usr/bin/env python3
"""List source-backed machine histories for Global Oil migration review."""
import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from etl_global_oil_domain import norm, split_machine_and_point
from load_historic_samples_via_api import sample_date, sample_validation_errors


def rows(path):
    return [json.loads(line)["data"] for line in path.open(encoding="utf-8") if line.strip()]


def main():
    parser = argparse.ArgumentParser(description="Genera inventario de máquinas con histórico de fechas de toma.")
    parser.add_argument("--artifacts", type=Path, default=Path("outputs/migracion_historica_global_oil"))
    args = parser.parse_args()
    groups, rejected = defaultdict(list), []
    for row in rows(args.artifacts / "staging" / "reportes_oa_raw.jsonl"):
        errors = sample_validation_errors(row)
        if errors:
            rejected.append({"oa": str(row.get("OA") or "").strip(), "motivos": " | ".join(errors)})
            continue
        company = norm(row.get("CLIENTE"))
        machine, point = split_machine_and_point(norm(row.get("EQUIPO")))
        groups[(company, machine)].append({
            "oa": str(row.get("OA") or "").strip(),
            "fecha_toma": sample_date(row),
            "punto": point,
            "equipo_origen": norm(row.get("EQUIPO")),
        })

    report_rows = []
    for (company, machine), records in groups.items():
        dates = sorted({record["fecha_toma"] for record in records})
        if len(dates) < 2:
            continue
        report_rows.append({
            "empresa": company,
            "maquina": machine,
            "muestras": len(records),
            "fechas_distintas": len(dates),
            "primera_fecha": dates[0],
            "ultima_fecha": dates[-1],
            "fechas_toma": " | ".join(dates),
            "oas": " | ".join(sorted({record["oa"] for record in records})),
            "puntos": " | ".join(sorted({record["punto"] for record in records if record["punto"]})),
        })
    report_rows.sort(key=lambda row: (-row["fechas_distintas"], row["empresa"], row["maquina"]))
    output = args.artifacts / "reports" / "maquinas_con_historico.csv"
    with output.open("w", newline="", encoding="utf-8-sig") as target:
        writer = csv.DictWriter(target, fieldnames=list(report_rows[0]) if report_rows else ["empresa", "maquina"])
        writer.writeheader()
        writer.writerows(report_rows)
    rejected_output = args.artifacts / "qa" / "muestras_omitidas_historial.csv"
    with rejected_output.open("w", newline="", encoding="utf-8-sig") as target:
        writer = csv.DictWriter(target, fieldnames=["oa", "motivos"])
        writer.writeheader(); writer.writerows(rejected)
    print(json.dumps({"machines_with_history": len(report_rows), "omitted_samples": len(rejected), "report": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

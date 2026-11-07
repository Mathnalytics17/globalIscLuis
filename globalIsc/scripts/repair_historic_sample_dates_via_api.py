#!/usr/bin/env python3
"""Reconcile already-imported sample dates from the raw OA source through API."""
import argparse
import json
from pathlib import Path

from load_global_oil_via_api import Api
from load_historic_samples_via_api import sample_date


def raw_rows(path):
    return [json.loads(line)["data"] for line in path.open(encoding="utf-8") if line.strip()]


def is_excel_serial(value):
    try:
        numeric = float(str(value or "").strip().replace(",", "."))
        return 1 <= numeric <= 60000
    except ValueError:
        return False


def patch(api, path, payload):
    token = api.session.cookies.get("csrftoken")
    response = api._request("patch", path, json=payload, headers={"X-CSRFToken": token or "", "Referer": api.base_url})
    if not response.ok:
        raise RuntimeError(f"API PATCH {path} ({response.status_code}): {response.text}")
    return response.json()


def main():
    parser = argparse.ArgumentParser(description="Corrige fechas históricas de muestras a partir del OA de origen.")
    parser.add_argument("--artifacts", type=Path, default=Path("outputs/migracion_historica_global_oil"))
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email"); parser.add_argument("--password"); parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    rows = raw_rows(args.artifacts / "staging" / "reportes_oa_raw.jsonl")
    candidates = [row for row in rows if is_excel_serial(row.get("FECHA TOMA DE MUESTRA"))]
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "oa": len(rows), "excel_serial_dates": len(candidates), "writes": False}, ensure_ascii=False))
        return
    if not args.email or not args.password:
        parser.error("--email y --password son obligatorios con --apply")
    def reconcile(row):
        oa = str(row.get("OA") or "").strip()
        expected = sample_date(row)
        api = Api(args.base_url, args.email, args.password)
        matches = api.get("lubrication/samples/", {"oa_origen": oa})
        if len(matches) != 1:
            raise RuntimeError(f"OA {oa}: se esperaba una muestra y llegaron {len(matches)}")
        sample = matches[0]
        actual = str(sample.get("fecha_toma") or "")[:10]
        if actual == expected:
            return None
        patch(api, f"lubrication/samples/{sample['id']}/", {"fecha_toma": expected})
        return {"oa": oa, "muestra": sample["id"], "anterior": actual, "fecha_toma": expected}

    changes = []
    for row in candidates:
        change = reconcile(row)
        if change:
            changes.append(change)
    report = args.artifacts / "reports" / "reparacion_fechas_historicas_api.json"
    report.write_text(json.dumps({"changed": changes, "count": len(changes)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"mode": "apply", "corrected": len(changes), "report": str(report)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

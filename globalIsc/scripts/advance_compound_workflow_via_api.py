#!/usr/bin/env python3
"""Advance imported samples through laboratory reception and compound-test assignment.

This uses the same API transitions as the UI.  The source ``Limit`` flag is
authoritative: SI activates the versioned source; No keeps the result
informative without a limit contract.
"""
import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from load_global_oil_via_api import Api


def json_rows(path):
    return json.loads(path.read_text(encoding="utf-8"))


def line_rows(path):
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def main():
    parser = argparse.ArgumentParser(description="Ingresa lotes y asigna ELEMENTOS/ESPUMA por API.")
    parser.add_argument("--artifacts", type=Path, default=Path("outputs/migracion_historica_global_oil"))
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email"); parser.add_argument("--password"); parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    import_audit = json_rows(args.artifacts / "reports" / "carga_api_muestras.json")
    result_payloads = line_rows(args.artifacts / "staging" / "api_result_payloads.jsonl")
    source = {str(row["data"].get("OA") or "").strip(): row["data"] for row in (json.loads(line) for line in (args.artifacts / "staging" / "reportes_oa_raw.jsonl").open(encoding="utf-8") if line.strip())}
    wanted = defaultdict(set)
    for item in result_payloads:
        wanted[str(item["oa"])].add(item["test_code"])
    # assign-batch is a synchronization endpoint: posting only the compound
    # set later would remove physical assignments (and vice versa).  Every
    # invocation therefore sends the complete desired test set for a sample.
    all_wanted = defaultdict(set, {oa: set(codes) for oa, codes in wanted.items()})
    physical_path = args.artifacts / "staging" / "api_result_payloads_physical.jsonl"
    if physical_path.is_file():
        for item in line_rows(physical_path):
            all_wanted[str(item["oa"])].add(item["test_code"])
    relevant = [item for item in import_audit if item["oa"] in all_wanted]
    batches = sorted({item["lote"] for item in import_audit})
    summary = {"mode": "dry_run", "batches_to_receive": len(batches), "samples_with_compounds": len(relevant), "compound_assignments": sum(len(wanted[item["oa"]]) for item in relevant), "limits": "source_Limit_SI", "writes": False}
    if not args.apply:
        print(json.dumps(summary, ensure_ascii=False)); return
    if not args.email or not args.password:
        parser.error("--email y --password son obligatorios con --apply")
    api = Api(args.base_url, args.email, args.password)
    tests = {item.get("acronimo"): item["id"] for item in api.get("lubrication/tests/", {"page_size": 500})}
    missing_tests = {code for codes in all_wanted.values() for code in codes} - set(tests)
    if missing_tests: raise RuntimeError(f"Faltan pruebas API: {sorted(missing_tests)}")
    by_batch = defaultdict(list)
    for item in relevant: by_batch[item["lote"]].append(item)
    receptions, assignments = [], []
    # The API exposes batches that have not entered the laboratory yet.  Using
    # it makes a stopped ETL resumable: a prior reception is never POSTed a
    # second time, while assignment synchronization below remains idempotent.
    pending_receptions = {
        str(item.get("id"))
        for item in api.get("lubrication/lab-batch-entries/available-batches/")
    }
    for batch_id in batches:
        if str(batch_id) in pending_receptions:
            api.post("lubrication/lab-batch-entries/", {
                "lote": batch_id, "fecha_recepcion": "2026-09-20",
                "condiciones_entrega": "Ingreso histórico por ETL Global Oil.",
                "observaciones": "Recepción reproducible para migración histórica.",
                "campos_adicionales": {"origen": "ETL histórica Global Oil"},
            })
            receptions.append(batch_id)
        items = by_batch.get(batch_id, [])
        if not items:
            continue
        groups = defaultdict(list)
        for item in items:
            apply_limits = str(source[item["oa"]].get("Limit") or "").strip().casefold() not in {"no", "n", "false", "0"}
            groups[(tuple(sorted(all_wanted[item["oa"]])), apply_limits)].append(item["muestra"])
        for (codes, apply_limits), sample_ids in groups.items():
            response = api.post("lubrication/sample-tests/assign-batch/", {"lote_id": batch_id, "sample_ids": sample_ids, "estado_asignacion": "confirmada", "pruebas": [{"prueba": tests[code], "aplicar_limites": apply_limits} for code in codes]})
            assignments.append({"lote": batch_id, "created": response.get("created_count", 0), "samples": len(sample_ids), "tests": codes, "aplicar_limites": apply_limits})
    sample_test_map = defaultdict(dict)
    for batch_id, items in by_batch.items():
        by_sample = {item["muestra"]: item["oa"] for item in items}
        for item in api.get(f"lubrication/sample-tests/by-batch/{batch_id}/"):
            oa = by_sample.get(item.get("muestra"))
            code = (item.get("prueba") or {}).get("acronimo")
            if oa and code in all_wanted[oa]: sample_test_map[oa][code] = item["id"]
    # Only samples that passed the intake validation can have assignments.
    expected = sum(len(all_wanted[item["oa"]]) for item in relevant)
    actual = sum(len(values) for values in sample_test_map.values())
    if expected != actual:
        raise RuntimeError(f"Mapa incompleto de pruebas muestra: {actual}/{expected}")
    map_path = args.artifacts / "staging" / "oa_pruebas_muestra.json"
    map_path.write_text(json.dumps(sample_test_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path = args.artifacts / "reports" / "carga_api_flujo_compuestos.json"
    report_path.write_text(json.dumps({"recepciones": receptions, "asignaciones": assignments, "limites": summary["limits"]}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary.update({"mode": "apply", "writes": True, "received": len(receptions), "assigned": actual, "sample_test_map": str(map_path)})
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

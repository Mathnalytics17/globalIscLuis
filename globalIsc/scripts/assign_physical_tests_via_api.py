#!/usr/bin/env python3
"""Assign exact physical-test sets to historical samples through the API."""
import argparse, json
from collections import defaultdict
from pathlib import Path
from load_global_oil_via_api import Api

def lines(path): return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]

def main():
    p = argparse.ArgumentParser(description="Asigna pruebas físicas históricas por API.")
    p.add_argument("--artifacts", type=Path, default=Path("outputs/migracion_historica_global_oil")); p.add_argument("--base-url", default="http://localhost:8000")
    p.add_argument("--email"); p.add_argument("--password"); p.add_argument("--apply", action="store_true"); a = p.parse_args()
    imported = json.loads((a.artifacts / "reports" / "carga_api_muestras.json").read_text(encoding="utf-8")); payloads = lines(a.artifacts / "staging" / "api_result_payloads_physical.jsonl")
    source = {str(json.loads(line)["data"].get("OA") or "").strip(): json.loads(line)["data"] for line in (a.artifacts / "staging" / "reportes_oa_raw.jsonl").open(encoding="utf-8") if line.strip()}
    wanted = defaultdict(set)
    for row in payloads: wanted[str(row["oa"])].add(row["test_code"])
    # Keep compound assignments in the synchronization contract as well.
    # assign-batch replaces the sample's set; it is not an additive endpoint.
    all_wanted = defaultdict(set, {oa: set(codes) for oa, codes in wanted.items()})
    for row in lines(a.artifacts / "staging" / "api_result_payloads.jsonl"):
        all_wanted[str(row["oa"])].add(row["test_code"])
    by_batch = defaultdict(list)
    for row in imported:
        if row["oa"] in all_wanted: by_batch[row["lote"]].append(row)
    summary = {"mode":"dry_run", "payloads":len(payloads), "samples":len(wanted), "batches":len(by_batch), "writes":False}
    if not a.apply: print(json.dumps(summary, ensure_ascii=False)); return
    if not a.email or not a.password: p.error("--email y --password son obligatorios con --apply")
    api = Api(a.base_url, a.email, a.password); tests = {item.get("acronimo"): item["id"] for item in api.get("lubrication/tests/", {"page_size":500})}
    missing = {code for codes in all_wanted.values() for code in codes} - set(tests)
    if missing: raise RuntimeError(f"Pruebas físicas no encontradas: {sorted(missing)}")
    created = 0
    for batch_id, samples in by_batch.items():
        groups = defaultdict(list)
        for sample in samples:
            apply_limits = str(source[sample["oa"]].get("Limit") or "").strip().casefold() not in {"no", "n", "false", "0"}
            groups[(tuple(sorted(all_wanted[sample["oa"]])), apply_limits)].append(sample["muestra"])
        for (codes, apply_limits), sample_ids in groups.items():
            response = api.post("lubrication/sample-tests/assign-batch/", {"lote_id":batch_id,"sample_ids":sample_ids,"estado_asignacion":"confirmada","pruebas":[{"prueba":tests[code],"aplicar_limites":apply_limits} for code in codes]})
            created += response.get("created_count", 0)
    map_path = a.artifacts / "staging" / "oa_pruebas_muestra.json"; mapping = defaultdict(dict)
    for batch_id, samples in by_batch.items():
        oa_by_sample = {row["muestra"]:row["oa"] for row in samples}
        for assigned in api.get(f"lubrication/sample-tests/by-batch/{batch_id}/"):
            oa = oa_by_sample.get(assigned.get("muestra")); code = (assigned.get("prueba") or {}).get("acronimo")
            if oa and code in all_wanted[oa]: mapping[oa][code] = assigned["id"]
    imported_oas = {row["oa"] for rows in by_batch.values() for row in rows}
    expected = sum(len(all_wanted[oa]) for oa in imported_oas); actual = sum(1 for oa in imported_oas for code in all_wanted[oa] if code in mapping.get(oa,{}))
    if actual != expected: raise RuntimeError(f"Mapa físico incompleto: {actual}/{expected}")
    map_path.write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary.update({"mode":"apply","writes":True,"created":created,"mapped":actual}); print(json.dumps(summary,ensure_ascii=False))

if __name__ == "__main__": main()

#!/usr/bin/env python3
"""Submit compound-result staging through result-entry API forms only."""
import argparse
import json
import math
import os
from pathlib import Path

from load_global_oil_via_api import Api


def rows(path):
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def json_rows(path):
    return json.loads(path.read_text(encoding="utf-8"))


def finite_number(value):
    """Return a finite number, without turning detection limits into measurements."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        text = str(value or "").strip()
        if not text or text.startswith(("<", ">", "≤", "≥")) or text in {"-", "N/A", "NA"}:
            return None
        try:
            number = float(text.replace(",", "."))
        except ValueError:
            return None
    return number if math.isfinite(number) else None


def main():
    parser = argparse.ArgumentParser(description="Ingresa ELEMENTOS/ESPUMA mediante el formulario API.")
    parser.add_argument("--artifacts", type=Path, default=Path("outputs/migracion_historica_global_oil"))
    parser.add_argument("--sample-test-map", type=Path, required=True, help="JSON {OA: {ELEMENTOS: prueba_muestra_id, ESPUMA: prueba_muestra_id}}")
    parser.add_argument("--payload-file", default="api_result_payloads.jsonl")
    parser.add_argument("--report-file", default="carga_api_resultados_compuestos.json")
    parser.add_argument("--test-code", help="Restringe la carga a una prueba; útil al reconstruir una estructura.")
    parser.add_argument("--skip-locked", action="store_true", help="Conserva lotes ya revisados/reportados al recargar una estructura.")
    parser.add_argument("--shard-count", type=int, default=1, help="Cantidad de particiones determinísticas para una API con varios workers.")
    parser.add_argument("--shard-index", type=int, default=0, help="Índice de esta partición, desde cero.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email"); parser.add_argument("--password"); parser.add_argument("--password-env", help="Nombre de variable de entorno que contiene la contraseña."); parser.add_argument("--apply", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Omite formularios ya guardados por una ejecución interrumpida.")
    parser.add_argument("--batch-shard-count", type=int, default=1, help="Particiones deterministas por lote; nunca divide un lote.")
    parser.add_argument("--batch-shard-index", type=int, default=0, help="Índice de partición, desde cero.")
    parser.add_argument("--seed-from-api", action="store_true", help="Construye el checkpoint consultando el estado de pruebas por lote vía API.")
    args = parser.parse_args()
    if not args.password and args.password_env:
        args.password = os.environ.get(args.password_env)
    payload_path = args.artifacts / "staging" / args.payload_file
    payloads = rows(payload_path)
    if args.test_code:
        payloads = [item for item in payloads if item.get("test_code") == args.test_code]
    if args.shard_count < 1 or not 0 <= args.shard_index < args.shard_count:
        parser.error("--shard-index debe estar entre 0 y --shard-count - 1")
    if args.batch_shard_count < 1 or not 0 <= args.batch_shard_index < args.batch_shard_count:
        parser.error("--batch-shard-index debe estar entre 0 y --batch-shard-count - 1")
    payloads = [item for index, item in enumerate(payloads) if index % args.shard_count == args.shard_index]
    mapping = json.loads(args.sample_test_map.read_text(encoding="utf-8")) if args.sample_test_map.is_file() else parser.error("No existe el mapa OA/prueba_muestra.")
    # Rows rejected before intake intentionally have no sample-test mapping.
    payloads = [item for item in payloads if str(item["oa"]) in mapping]
    missing = [item for item in payloads if str(item["oa"]) not in mapping or item["test_code"] not in mapping[str(item["oa"])] ]
    if missing:
        parser.error(f"Faltan {len(missing)} asignaciones en el mapa OA/prueba_muestra.")
    batch_by_oa = {str(item["oa"]): item["lote"] for item in json_rows(args.artifacts / "reports" / "carga_api_muestras.json")}
    batches = sorted({batch_by_oa[str(item["oa"])] for item in payloads})
    selected_batches = {batch for index, batch in enumerate(batches) if index % args.batch_shard_count == args.batch_shard_index}
    payloads = [item for item in payloads if batch_by_oa[str(item["oa"])] in selected_batches]
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "payloads": len(payloads), "missing": 0, "writes": False})); return
    if not args.email or not args.password: parser.error("--email y --password son obligatorios con --apply")
    api = Api(args.base_url, args.email, args.password)
    report_path = args.artifacts / "reports" / args.report_file
    audit = json_rows(report_path) if args.resume and report_path.is_file() else []
    done = {(str(item["oa"]), item["test"]) for item in audit}
    if args.seed_from_api:
        by_batch = {}
        for item in payloads:
            by_batch.setdefault(batch_by_oa[str(item["oa"])], []).append(item)
        for batch, batch_payloads in by_batch.items():
            statuses = {str(row["id"]): row.get("estatus") for row in api.get(f"lubrication/result-entry/batches/{batch}/").get("sample_tests", [])}
            for item in batch_payloads:
                key = (str(item["oa"]), item["test_code"])
                sample_test_id = str(mapping[str(item["oa"])][item["test_code"]])
                if key not in done and statuses.get(sample_test_id) not in {None, "pendiente"}:
                    audit.append({"oa": item["oa"], "test": item["test_code"], "prueba_muestra": sample_test_id, "values": len(item["values"]), "skipped": True, "source": "api_batch_status"})
                    done.add(key)
        report_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for item in payloads:
        if (str(item["oa"]), item["test_code"]) in done:
            continue
        sample_test_id = mapping[str(item["oa"])][item["test_code"]]
        form = api.get(f"lubrication/result-entry/sample-tests/{sample_test_id}/form/")
        if args.resume and (form.get("current_result") or {}).get("payload"):
            audit.append({"oa": item["oa"], "test": item["test_code"], "prueba_muestra": sample_test_id, "values": len(item["values"]), "skipped": True})
            report_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            continue
        fields = {(field.get("resultado_nombre"), field.get("componente_nombre")): field for field in form["fields"]}
        values = []
        skipped_invalid_values = []
        for value in item["values"]:
            field = fields.get((value["result_code"], value["component_code"]))
            if not field:
                raise RuntimeError(f"OA {item['oa']} / {item['test_code']}: campo API no encontrado {value['result_code']}/{value['component_code']}")
            submitted_value = value["value"]
            if str(field.get("tipo_dato") or "").lower() in {"numerico", "numeric", "number"}:
                submitted_value = finite_number(value["value"])
                if submitted_value is None:
                    skipped_invalid_values.append({"key": field["key"], "source_value": value["value"], "reason": "non_numeric_source_value"})
                    continue
            values.append({"key": field["key"], "value": submitted_value, "observacion": "Importación histórica Global Oil"})
        if not values:
            audit.append({"oa": item["oa"], "test": item["test_code"], "prueba_muestra": sample_test_id, "values": 0, "skipped_invalid_values": skipped_invalid_values})
            report_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            continue
        try:
            api.post(f"lubrication/result-entry/sample-tests/{sample_test_id}/save-draft/", {"values": values, "observaciones": "Importación histórica Global Oil"})
        except RuntimeError as error:
            if args.skip_locked and "no esta disponible para el estado actual" in str(error):
                audit.append({"oa": item["oa"], "test": item["test_code"], "prueba_muestra": sample_test_id, "values": 0, "skipped_locked": True})
                continue
            raise
        audit.append({"oa": item["oa"], "test": item["test_code"], "prueba_muestra": sample_test_id, "values": len(values), "skipped_invalid_values": skipped_invalid_values})
        report_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"mode": "apply", "submitted": len(audit), "writes": True}))


if __name__ == "__main__": main()

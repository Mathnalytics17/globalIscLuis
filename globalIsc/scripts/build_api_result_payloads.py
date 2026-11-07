#!/usr/bin/env python3
"""Convert compound staging into API result-entry payloads without DB writes."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, default=Path("outputs/migracion_historica_global_oil"))
    args = parser.parse_args()
    source = args.artifacts / "staging" / "resultados_compuestos.jsonl"
    if not source.is_file(): parser.error("Ejecute etl_global_oil_domain.py primero.")
    payloads = []
    for line in source.open(encoding="utf-8"):
        row = json.loads(line)
        if row["elements"]:
            payloads.append({"oa": row["oa"], "test_code": "ELEMENTOS", "values": [{"result_code": element, "component_code": element, "value": value} for element, value in row["elements"].items()]})
        if row["foam"]:
            values = []
            for sequence, components in row["foam"].items():
                for component, value in components.items():
                    if component != "source_value": values.append({"result_code": sequence, "component_code": component, "value": value})
            payloads.append({"oa": row["oa"], "test_code": "ESPUMA", "values": values})
    target = args.artifacts / "staging" / "api_result_payloads.jsonl"
    with target.open("w", encoding="utf-8") as out:
        for payload in payloads: out.write(json.dumps(payload, ensure_ascii=False) + "\n")
    print(json.dumps({"payloads": len(payloads), "path": str(target)}, ensure_ascii=False))


if __name__ == "__main__": main()

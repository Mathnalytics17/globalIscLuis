#!/usr/bin/env python3
"""Verify published technical limit configurations through the public API.

The check specifically prevents a silent UI failure where a criterion contains
values under a key that does not exist in the source's limit fields.
"""
import argparse
import json
from pathlib import Path

from load_global_oil_via_api import Api


def main():
    parser = argparse.ArgumentParser(description="Valida correspondencia entre campos y criterios de límites.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email")
    parser.add_argument("--password")
    parser.add_argument("--apply", action="store_true", help="Autoriza la lectura autenticada de la API.")
    parser.add_argument("--artifacts", type=Path, default=Path("outputs/migracion_historica_global_oil"))
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "check": "criterion_keys_are_limit_fields", "writes": False}, ensure_ascii=False))
        return
    if not args.email or not args.password:
        parser.error("--email y --password son obligatorios con --apply")

    api = Api(args.base_url, args.email, args.password)
    sources = api.get("technical-config/limit-sources/", {"page_size": 100})
    findings = []
    for source in sources:
        # Older versions deliberately remain available as history.  They are
        # not resolved by the operational workflow and must not fail the
        # validation of the current ETL configuration.
        if not source.get("activo", False):
            continue
        fields = {field["codigo"] for field in source.get("campos_limite", [])}
        criterion_keys = {
            key
            for criterion in source.get("criterios", [])
            for key in criterion.get("valores_limite", {}).keys()
        }
        invalid = sorted(criterion_keys - fields)
        if invalid:
            findings.append({
                "source_id": source["id"],
                "test": source["prueba_info"]["acronimo"],
                "invalid_criterion_keys": invalid,
                "field_codes": sorted(fields),
            })

    report = args.artifacts / "reports" / "validacion_configuracion_limites_api.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "valid": not findings,
        "checked_sources": sum(1 for source in sources if source.get("activo", False)),
        "historical_sources_ignored": sum(1 for source in sources if not source.get("activo", False)),
        "findings": findings,
    }
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({**payload, "report": str(report)}, ensure_ascii=False))
    if findings:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Create the historical ELEMENTOS and ESPUMA test structures through the API.

The script is intentionally idempotent: a test is identified by acronym and is
never overwritten.  Updating a technical structure must be an explicit,
reviewed operation, not an accidental consequence of re-running an import.
"""
import argparse
import json

from load_global_oil_via_api import Api


METALS = (
    "Ag", "Al", "B", "Ba", "Ca", "Cd", "Cr", "Cu", "Fe", "K", "Li", "Mg",
    "Mn", "Mo", "Na", "Ni", "P", "Pb", "Sb", "Si", "Sn", "Ti", "V", "Zn",
)


def scalar_result(name, acronym, unit, order):
    return {
        "temp_id": f"result-{acronym}", "nombre": name, "acronimo": acronym,
        "unidad_medida": unit, "orden": order, "activo": True,
        "divisiones": [{
            "temp_id": f"division-{acronym}", "nombre": None,
            "es_principal": True, "orden": 1, "activo": True,
            "componentes": [{
                "temp_id": f"component-{acronym}", "nombre": name,
                "acronimo": acronym, "tipo_dato": "numerico", "orden": 1,
                "activo": True,
            }], "separadores": [], "disposiciones": [],
        }],
    }


def elements_payload():
    return {
        "nombre_variable": "Elementos", "acronimo": "ELEMENTOS", "unidad_medida": "ppm",
        "activo": True,
        "resultados": [scalar_result(metal, metal, "ppm", index) for index, metal in enumerate(METALS, 1)],
    }


def foam_payload():
    resultados = []
    for order, (sequence, first, second) in enumerate((
        ("Secuencia I", "EI", "FI"), ("Secuencia II", "EII", "FII"), ("Secuencia III", "EIII", "FIII"),
    ), 1):
        resultados.append({
            "temp_id": f"result-{order}", "nombre": sequence, "acronimo": f"ESPUMA_{order}",
            "unidad_medida": "mL/mL", "orden": order, "activo": True,
            "divisiones": [{
                "temp_id": f"division-{order}", "nombre": None, "es_principal": True,
                "orden": 1, "activo": True,
                "componentes": [
                    {"temp_id": f"component-{first}", "nombre": first, "acronimo": first, "tipo_dato": "numerico", "orden": 1, "activo": True},
                    {"temp_id": f"component-{second}", "nombre": second, "acronimo": second, "tipo_dato": "numerico", "orden": 2, "activo": True},
                ], "separadores": [], "disposiciones": [],
            }],
        })
    return {"nombre_variable": "Espuma", "acronimo": "ESPUMA", "unidad_medida": "mL/mL", "activo": True, "resultados": resultados}


def main():
    parser = argparse.ArgumentParser(description="Crea pruebas compuestas históricas por API.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email"); parser.add_argument("--password")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    payloads = [elements_payload(), foam_payload()]
    summary = {"tests": [item["acronimo"] for item in payloads], "result_fields": 30, "mode": "dry_run", "writes": False}
    if not args.apply:
        print(json.dumps(summary, ensure_ascii=False)); return
    if not args.email or not args.password:
        parser.error("--email y --password son obligatorios con --apply")
    api = Api(args.base_url, args.email, args.password)
    existing = {str(item.get("acronimo", "")).upper(): item for item in api.get("lubrication/tests/", {"include_structure": "true", "page_size": 500})}
    created, preserved = [], []
    for payload in payloads:
        acronym = payload["acronimo"]
        if acronym in existing:
            preserved.append({"acronimo": acronym, "id": existing[acronym].get("id")})
        else:
            created_test = api.post("lubrication/tests/", payload)
            created.append({"acronimo": acronym, "id": created_test.get("id")})
    summary.update({"mode": "apply", "writes": True, "created": created, "preserved": preserved})
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

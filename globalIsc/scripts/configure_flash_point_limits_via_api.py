#!/usr/bin/env python3
"""Create source-backed PUNTO_CHISPA minima by performance specification."""
import argparse
import json
import re
import unicodedata
from pathlib import Path

from load_global_oil_via_api import Api


def one(rows, predicate, label):
    found = [row for row in rows if predicate(row)]
    if len(found) != 1:
        raise RuntimeError(f"{label}: {len(found)} registros")
    return found[0]


def field_code(*parts):
    normalized = []
    for part in parts:
        ascii_value = unicodedata.normalize("NFKD", str(part)).encode("ascii", "ignore").decode("ascii").lower()
        normalized.append(re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_"))
    return "_".join(part for part in normalized if part)


def main():
    parser = argparse.ArgumentParser(description="Carga mínimos de punto de chispa por nivel de desempeño.")
    parser.add_argument("--artifacts", type=Path, default=Path("outputs/migracion_historica_global_oil"))
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email"); parser.add_argument("--password"); parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({"mode": "dry_run", "test": "PUNTO_CHISPA", "catalog": "NIVEL_DESEMPENO", "rule": "min", "writes": False}, ensure_ascii=False))
        return
    if not args.email or not args.password:
        parser.error("--email y --password son obligatorios con --apply")

    api = Api(args.base_url, args.email, args.password)
    test = one(api.get("lubrication/tests/", {"search": "PUNTO_CHISPA", "include_structure": "true", "page_size": 100}), lambda row: row.get("acronimo") == "PUNTO_CHISPA", "Prueba punto de chispa")
    catalog = one(api.get("technical-config/catalogs/", {"search": "nivel_desempeno"}), lambda row: row.get("codigo") == "nivel_desempeno", "Catálogo nivel de desempeño")
    sample_field = one(api.get("technical-config/sample-fields/", {"search": "nivel_desempeno"}), lambda row: row.get("codigo") == "nivel_desempeno", "Campo técnico desempeño")
    result = test["resultados"][0]; division = result["divisiones"][0]; component = division["componentes"][0]
    leaf = {
        "codigo": field_code(result["nombre"], component["nombre"]), "nombre": test["nombre_variable"],
        "resultado": result["id"], "division": division["id"], "componente": component["id"], "unidad": "°C",
    }
    criteria = []
    for item in catalog["items"]:
        values = {value["campo_info"]["codigo"]: value["valor"] for value in item["valores"]}
        minimum = values.get("punto_chispa_min")
        if not minimum:
            continue
        criteria.append({
            "nombre": item["nombre"], "codigo": f"desempeno_{item['codigo']}", "tipo_criterio": "catalogo_item",
            "catalogo_item": item["id"], "valor": item["nombre"],
            "valores": {leaf["codigo"]: {"operador": "min", "min_aceptable": minimum, "usar_amarillo": False}},
            "selecciones_catalogo": [{"catalogo": catalog["id"], "item": item["id"]}],
        })
    payload = {
        "prueba": test["id"], "fuente": "catalogos", "catalogos": [{"catalogo": catalog["id"], "campo_tecnico_muestra": sample_field["id"]}],
        "modo_seleccion": "desde_muestra_editable", "publicar": True,
        "decision": {"nombre": "Punto de chispa por especificación", "campos": []},
        "campos": [{**leaf, "origen_limite": "catalogo", "operador": "min", "tipo_comparacion": "numerica", "participa": True, "evalua": True}],
        "criterios": criteria,
    }
    response = api.post("technical-config/limit-sources/configure/", payload)
    report = args.artifacts / "reports" / "configuracion_limites_punto_chispa_api.json"
    report.write_text(json.dumps({"response": response, "criteria": criteria}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"mode": "apply", "source_id": response["id"], "version": response["version"], "criteria": len(criteria), "report": str(report)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Create the physical-test catalog through the public API, idempotently."""
import argparse
import json

from load_global_oil_via_api import Api
from physical_measurement_schema import PHYSICAL_MEASUREMENTS, COMPOUND_PHYSICAL_MEASUREMENTS


def payload(source, acronym, name, unit, data_type):
    return {
        "nombre_variable": name, "acronimo": acronym, "unidad_medida": unit or None, "activo": True,
        "resultados": [{
            "temp_id": f"result-{acronym}", "nombre": name, "acronimo": acronym,
            "unidad_medida": unit or None, "orden": 1, "activo": True,
            "divisiones": [{
                "temp_id": f"division-{acronym}", "nombre": None, "es_principal": True, "orden": 1, "activo": True,
                "componentes": [{"temp_id": f"component-{acronym}", "nombre": name, "acronimo": acronym, "tipo_dato": data_type, "orden": 1, "activo": True}],
                "separadores": [], "disposiciones": [],
            }],
        }],
    }


def compound_payload(source, acronym, name, unit, components):
    return {
        "nombre_variable": name, "acronimo": acronym, "unidad_medida": unit, "activo": True,
        "resultados": [{
            "temp_id": f"result-{acronym}", "nombre": name, "acronimo": acronym,
            "unidad_medida": unit, "orden": 1, "activo": True,
            "divisiones": [{
                "temp_id": f"division-{acronym}", "nombre": None, "es_principal": True, "orden": 1, "activo": True,
                # ISO source rows can explicitly omit one channel (e.g.
                # */21/21).  The ETL must preserve that absence rather than
                # fabricate a value, while allowing the reported channels.
                "componentes": [{"temp_id": f"component-{acronym}-{component}", "nombre": component, "acronimo": component, "tipo_dato": "numerico", "requiere_valor": False, "orden": index, "activo": True} for index, component in enumerate(components, start=1)],
                "separadores": [], "disposiciones": [],
            }],
        }],
    }


def main():
    parser = argparse.ArgumentParser(description="Crea catálogo de mediciones físicas por API.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email"); parser.add_argument("--password"); parser.add_argument("--apply", action="store_true")
    parser.add_argument("--rebuild-iso4406", action="store_true", help="Reemplaza la estructura histórica textual por 4/6/14 µm; después recargue sus resultados.")
    args = parser.parse_args()
    definitions = [payload(*definition) for definition in PHYSICAL_MEASUREMENTS] + [compound_payload(*definition) for definition in COMPOUND_PHYSICAL_MEASUREMENTS]
    summary = {"mode": "dry_run", "tests": len(definitions), "numeric": sum(item[-1] == "numerico" for item in PHYSICAL_MEASUREMENTS) + 1, "text": sum(item[-1] == "texto" for item in PHYSICAL_MEASUREMENTS), "iso4406_components": 3, "writes": False}
    if not args.apply:
        print(json.dumps(summary, ensure_ascii=False)); return
    if not args.email or not args.password: parser.error("--email y --password son obligatorios con --apply")
    api = Api(args.base_url, args.email, args.password)
    existing = {str(item.get("acronimo", "")).upper(): item for item in api.get("lubrication/tests/", {"page_size": 500})}
    created, preserved = [], []
    for definition in definitions:
        code = definition["acronimo"]
        if code not in existing: created.append(api.post("lubrication/tests/", definition).get("id"))
        elif code == "NIVEL_CONTAMINACION" and args.rebuild_iso4406:
            token = api.session.cookies.get("csrftoken")
            response = api._request("patch", f"lubrication/tests/{existing[code]['id']}/", json=definition, headers={"X-CSRFToken": token or "", "Referer": api.base_url})
            if not response.ok: raise RuntimeError(f"No se pudo reconstruir ISO 4406: {response.status_code} {response.text}")
            created.append(existing[code]["id"])
        else: preserved.append(code)
    summary.update({"mode": "apply", "writes": True, "created": len(created), "preserved": len(preserved), "iso4406_rebuilt": bool(args.rebuild_iso4406)})
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__": main()

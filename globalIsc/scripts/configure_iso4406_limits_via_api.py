#!/usr/bin/env python3
"""Create the ISO 4406 upper-bound limit source through the public API."""
import argparse
import json
from pathlib import Path

from load_global_oil_via_api import Api


def one(rows, predicate, label):
    found = [row for row in rows if predicate(row)]
    if len(found) != 1:
        raise RuntimeError(f"{label}: se esperó 1 registro y llegaron {len(found)}")
    return found[0]


def main():
    parser = argparse.ArgumentParser(description="Configura ISO 4406 como 4/6/14 µm con máximo por componente.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email"); parser.add_argument("--password"); parser.add_argument("--apply", action="store_true")
    parser.add_argument("--artifacts", type=Path, default=Path("outputs/migracion_historica_global_oil"))
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps({"mode":"dry_run","test":"NIVEL_CONTAMINACION","rule":"max","components":["4um","6um","14um"],"criteria":7,"writes":False},ensure_ascii=False)); return
    if not args.email or not args.password: parser.error("--email y --password son obligatorios con --apply")
    api = Api(args.base_url, args.email, args.password)
    test = one(api.get("lubrication/tests/", {"search":"NIVEL_CONTAMINACION", "include_structure":"true", "page_size":100}), lambda row: row.get("acronimo") == "NIVEL_CONTAMINACION", "Prueba ISO 4406")
    catalog = one(api.get("technical-config/catalogs/", {"search":"nivel_contaminacion"}), lambda row: row.get("codigo") == "nivel_contaminacion", "Catálogo ISO")
    sample_field = one(api.get("technical-config/sample-fields/", {"search":"nivel_contaminacion"}), lambda row: row.get("codigo") == "nivel_contaminacion", "Campo técnico ISO")
    leaves = []
    for result in test["resultados"]:
        for division in result["divisiones"]:
            for component in division["componentes"]:
                leaves.append({"codigo": f"nivel_de_contaminacion_{component['acronimo']}", "nombre": f"Nivel de contaminación {component['acronimo']}", "resultado":result["id"], "division":division["id"], "componente":component["id"], "unidad":"ISO 4406"})
    by_component = {leaf["codigo"].rsplit("_", 1)[-1]: leaf for leaf in leaves}
    if set(by_component) != {"4um","6um","14um"}: raise RuntimeError(f"Estructura ISO inválida: {sorted(by_component)}")
    criteria=[]
    for item in catalog["items"]:
        values={value["campo_info"]["codigo"]:value["valor"] for value in item["valores"]}
        criteria.append({
            "nombre":item["nombre"], "codigo":f"iso_{item['codigo']}", "tipo_criterio":"catalogo_item", "catalogo_item":item["id"], "valor":item["nombre"],
            "valores":{by_component[key]["codigo"]:{"operador":"max","max_aceptable":values[key],"usar_amarillo":False} for key in ("4um","6um","14um")},
            "selecciones_catalogo":[{"catalogo":catalog["id"],"item":item["id"]}],
        })
    payload={
        "prueba":test["id"], "fuente":"catalogos", "catalogos":[{"catalogo":catalog["id"],"campo_tecnico_muestra":sample_field["id"]}],
        "modo_seleccion":"desde_muestra_editable", "publicar":True,
        "decision":{"nombre":"ISO 4406 máximo por componente","campos":[]},
        "campos":[{**leaf,"origen_limite":"catalogo","operador":"max","tipo_comparacion":"numerica","participa":True,"evalua":True} for leaf in leaves],
        "criterios":criteria,
    }
    result=api.post("technical-config/limit-sources/configure/",payload)
    report=args.artifacts/"reports"/"configuracion_limites_iso4406_api.json"; report.write_text(json.dumps({"payload":payload,"response":result},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"mode":"apply","source_id":result["id"],"version":result["version"],"criteria":len(criteria),"fields":len(leaves),"rule":"max","report":str(report)},ensure_ascii=False))


if __name__ == "__main__": main()

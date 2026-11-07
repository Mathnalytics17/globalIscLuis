#!/usr/bin/env python3
"""Configure index-of-viscosity limits from IV mono/multi catalog attributes."""
import argparse
import json
import re
import unicodedata
from pathlib import Path

from load_global_oil_via_api import Api


def one(rows, predicate, label):
    found = [row for row in rows if predicate(row)]
    if len(found) != 1: raise RuntimeError(f"{label}: {len(found)} registros")
    return found[0]


def code(*parts):
    return "_".join(re.sub(r"[^a-z0-9]+", "_", unicodedata.normalize("NFKD", str(part)).encode("ascii", "ignore").decode("ascii").lower()).strip("_") for part in parts)


def range_values(value):
    numbers = re.findall(r"\d+(?:[.,]\d+)?", str(value or ""))
    return [number.replace(",", ".") for number in numbers]


def rule_for(values):
    family = str(values.get("familia") or "").casefold()
    mono, multi = range_values(values.get("iv_mono")), range_values(values.get("iv_multi"))
    # Source note for Industrial ISO states "140 tope / 90 piso".  For
    # multigrades, a written a-b value is an inclusive range; a single IV
    # multi value is its minimum.  A single IV mono value is its maximum.
    if multi and len(multi) == 2: return {"operador": "between", "min_aceptable": multi[0], "max_aceptable": multi[1], "usar_amarillo": False}
    if mono and multi: return {"operador": "between", "min_aceptable": multi[0], "max_aceptable": mono[0], "usar_amarillo": False}
    if multi: return {"operador": "min", "min_aceptable": multi[0], "usar_amarillo": False}
    if mono: return {"operador": "max", "max_aceptable": mono[0], "usar_amarillo": False}
    return None


def main():
    parser=argparse.ArgumentParser(description="Carga índice de viscosidad por grado.")
    parser.add_argument("--artifacts", type=Path, default=Path("outputs/migracion_historica_global_oil")); parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--email"); parser.add_argument("--password"); parser.add_argument("--apply", action="store_true"); args=parser.parse_args()
    if not args.apply: print(json.dumps({"mode":"dry_run","test":"INDICE_VISCOSIDAD","catalog":"GRADO_VISCOSIDAD","writes":False},ensure_ascii=False)); return
    if not args.email or not args.password: parser.error("--email y --password son obligatorios con --apply")
    api=Api(args.base_url,args.email,args.password)
    test=one(api.get("lubrication/tests/",{"search":"INDICE_VISCOSIDAD","include_structure":"true","page_size":100}),lambda x:x.get("acronimo")=="INDICE_VISCOSIDAD","Prueba índice")
    catalog=one(api.get("technical-config/catalogs/",{"search":"grado_viscosidad"}),lambda x:x.get("codigo")=="grado_viscosidad","Catálogo grado")
    sample_field=one(api.get("technical-config/sample-fields/",{"search":"grado_viscosidad"}),lambda x:x.get("codigo")=="grado_viscosidad","Campo grado")
    result=test["resultados"][0]; division=result["divisiones"][0]; component=division["componentes"][0]
    leaf={"codigo":code(result["nombre"],component["nombre"]),"nombre":test["nombre_variable"],"resultado":result["id"],"division":division["id"],"componente":component["id"],"unidad":""}
    criteria=[]
    for item in catalog["items"]:
        values={value["campo_info"]["codigo"]:value["valor"] for value in item["valores"]}; rule=rule_for(values)
        if rule: criteria.append({"nombre":item["nombre"],"codigo":f"grado_{item['codigo']}","tipo_criterio":"catalogo_item","catalogo_item":item["id"],"valor":item["nombre"],"valores":{leaf["codigo"]:rule},"selecciones_catalogo":[{"catalogo":catalog["id"],"item":item["id"]}]})
    payload={"prueba":test["id"],"fuente":"catalogos","catalogos":[{"catalogo":catalog["id"],"campo_tecnico_muestra":sample_field["id"]}],"modo_seleccion":"desde_muestra_editable","publicar":True,"decision":{"nombre":"Índice de viscosidad por grado","campos":[]},"campos":[{**leaf,"origen_limite":"catalogo","operador":"between","tipo_comparacion":"numerica","participa":True,"evalua":True}],"criterios":criteria}
    response=api.post("technical-config/limit-sources/configure/",payload); report=args.artifacts/"reports"/"configuracion_limites_indice_viscosidad_api.json"; report.write_text(json.dumps({"response":response,"criteria":criteria},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"mode":"apply","source_id":response["id"],"version":response["version"],"criteria":len(criteria),"report":str(report)},ensure_ascii=False))


if __name__=="__main__": main()

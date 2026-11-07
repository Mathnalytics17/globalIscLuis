#!/usr/bin/env python3
"""Configure foam-sequence maxima by performance specification through API."""
import argparse, json, re, unicodedata
from pathlib import Path
from load_global_oil_via_api import Api

def one(rows, predicate, label):
    found=[row for row in rows if predicate(row)]
    if len(found)!=1: raise RuntimeError(f"{label}: {len(found)} registros")
    return found[0]
def code(*parts):
    return "_".join(re.sub(r"[^a-z0-9]+","_",unicodedata.normalize("NFKD",str(part)).encode("ascii","ignore").decode("ascii").lower()).strip("_") for part in parts)
def pair(value):
    values=str(value or "").strip().split("/")
    return values if len(values)==2 and all(re.fullmatch(r"\d+(?:[.,]\d+)?",x.strip()) for x in values) else None
def main():
    parser=argparse.ArgumentParser(description="Carga máximos de espuma por especificación.")
    parser.add_argument("--artifacts",type=Path,default=Path("outputs/migracion_historica_global_oil"));parser.add_argument("--base-url",default="http://localhost:8000");parser.add_argument("--email");parser.add_argument("--password");parser.add_argument("--apply",action="store_true");args=parser.parse_args()
    if not args.apply: print(json.dumps({"mode":"dry_run","test":"ESPUMA","catalog":"NIVEL_DESEMPENO","rule":"max","writes":False},ensure_ascii=False));return
    if not args.email or not args.password: parser.error("--email y --password son obligatorios con --apply")
    api=Api(args.base_url,args.email,args.password)
    test=one(api.get("lubrication/tests/",{"search":"ESPUMA","include_structure":"true","page_size":100}),lambda row:row.get("acronimo")=="ESPUMA","Prueba espuma")
    catalog=one(api.get("technical-config/catalogs/",{"search":"nivel_desempeno"}),lambda row:row.get("codigo")=="nivel_desempeno","Catálogo desempeño")
    sample_field=one(api.get("technical-config/sample-fields/",{"search":"nivel_desempeno"}),lambda row:row.get("codigo")=="nivel_desempeno","Campo desempeño")
    leaves=[]
    keys=("espuma_seq_i","espuma_seq_ii","espuma_seq_iii")
    for result,key in zip(test["resultados"],keys):
        division=result["divisiones"][0]
        for component in division["componentes"]:
            leaves.append({"catalog_key":key,"codigo":code(result["nombre"],component["nombre"]),"nombre":f"{result['nombre']} {component['nombre']}","resultado":result["id"],"division":division["id"],"componente":component["id"],"unidad":"mL/mL"})
    by_sequence={key:sorted([leaf for leaf in leaves if leaf["catalog_key"]==key],key=lambda leaf:leaf["componente"]) for key in keys}
    # Components were created with EI/EII/EIII first and FI/FII/FIII second.
    criteria=[]
    for item in catalog["items"]:
        values={value["campo_info"]["codigo"]:value["valor"] for value in item["valores"]}; limits={}
        for key in keys:
            source_pair=pair(values.get(key))
            if source_pair:
                for leaf,value in zip(by_sequence[key],source_pair): limits[leaf["codigo"]]={"operador":"max","max_aceptable":value.replace(",","."),"usar_amarillo":False}
        criteria.append({"nombre":item["nombre"],"codigo":f"desempeno_{item['codigo']}","tipo_criterio":"catalogo_item","catalogo_item":item["id"],"valor":item["nombre"],"valores":limits,"selecciones_catalogo":[{"catalogo":catalog["id"],"item":item["id"]}]})
    payload={"prueba":test["id"],"fuente":"catalogos","catalogos":[{"catalogo":catalog["id"],"campo_tecnico_muestra":sample_field["id"]}],"modo_seleccion":"desde_muestra_editable","publicar":True,"decision":{"nombre":"Espuma por especificación","campos":[]},"campos":[{k:v for k,v in leaf.items() if k!="catalog_key"}|{"origen_limite":"catalogo","operador":"max","tipo_comparacion":"numerica","participa":True,"evalua":True} for leaf in leaves],"criterios":criteria}
    response=api.post("technical-config/limit-sources/configure/",payload);report=args.artifacts/"reports"/"configuracion_limites_espuma_api.json";report.write_text(json.dumps({"response":response,"criteria":criteria},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"mode":"apply","source_id":response["id"],"version":response["version"],"criteria":len(criteria),"report":str(report)},ensure_ascii=False))
if __name__=="__main__":main()

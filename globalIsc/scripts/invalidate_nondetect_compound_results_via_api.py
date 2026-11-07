#!/usr/bin/env python3
"""Invalidate old all-<1 compound results through the result API audit flow."""
import argparse, json
from pathlib import Path
from load_global_oil_via_api import Api

def rows(path): return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]

def main():
    p=argparse.ArgumentParser(description="Invalida no-detecciones <1 cargadas antes de la regla de dominio.")
    p.add_argument("--artifacts",type=Path,default=Path("outputs/migracion_historica_global_oil"));p.add_argument("--base-url",default="http://localhost:8000");p.add_argument("--email");p.add_argument("--password");p.add_argument("--apply",action="store_true");a=p.parse_args()
    current={(str(x["oa"]),x["test_code"]) for x in rows(a.artifacts/"staging"/"api_result_payloads.jsonl")}
    previous=json.loads((a.artifacts/"reports"/"carga_api_resultados_compuestos.json").read_text(encoding="utf-8"))
    obsolete=[item for item in previous if (str(item["oa"]),item["test"]) not in current]
    summary={"mode":"dry_run","obsolete_results":len(obsolete),"writes":False}
    if not a.apply: print(json.dumps(summary,ensure_ascii=False));return
    if not a.email or not a.password:p.error("--email y --password son obligatorios con --apply")
    api=Api(a.base_url,a.email,a.password); invalidated=[]
    for item in obsolete:
        form=api.get(f"lubrication/result-entry/sample-tests/{item['prueba_muestra']}/form/"); result=form.get("current_result") or {}
        if result.get("id"):
            api.post(f"lubrication/result-entry/sample-tests/{item['prueba_muestra']}/save-draft/",{"values":[],"observaciones":"No detección <1: sin resultado según regla de migración."})
            api.post(f"lubrication/results/{result['id']}/invalidate/",{"reason":"No detección <1: no corresponde conservar un resultado histórico."})
            invalidated.append({"oa":item["oa"],"test":item["test"],"resultado":result["id"]})
    (a.artifacts/"reports"/"no_detecciones_invalidadas.json").write_text(json.dumps(invalidated,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary.update({"mode":"apply","writes":True,"invalidated":len(invalidated)});print(json.dumps(summary,ensure_ascii=False))
if __name__=="__main__":main()

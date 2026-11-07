#!/usr/bin/env python3
"""Advance imported history through confirm, review, interpretation and draft reports.

Every transition uses the public API.  Reports are generated but never approved,
published or emailed.
"""
import argparse, json, os
from collections import defaultdict
from pathlib import Path
from load_global_oil_via_api import Api


def raw_rows(path): return [json.loads(line)["data"] for line in path.open(encoding="utf-8") if line.strip()]


def main():
    p=argparse.ArgumentParser(description="Avanza históricos a reportes internos no aprobados por API.")
    p.add_argument("--artifacts",type=Path,default=Path("outputs/migracion_historica_global_oil"));p.add_argument("--base-url",default="http://localhost:8000")
    p.add_argument("--email");p.add_argument("--password");p.add_argument("--password-env");p.add_argument("--apply",action="store_true");p.add_argument("--resume",action="store_true");a=p.parse_args()
    if not a.password and a.password_env:
        a.password=os.environ.get(a.password_env)
    source={str(row.get("OA") or "").strip():row for row in raw_rows(a.artifacts/"staging"/"reportes_oa_raw.jsonl")}
    imports=json.loads((a.artifacts/"reports"/"carga_api_muestras.json").read_text(encoding="utf-8")); by_batch=defaultdict(list)
    for item in imports: by_batch[item["lote"]].append(item)
    summary={"mode":"dry_run","batches":len(by_batch),"samples":len(imports),"writes":False,"reports":"internal_unapproved"}
    if not a.apply: print(json.dumps(summary,ensure_ascii=False));return
    if not a.email or not a.password:p.error("--email y --password son obligatorios con --apply")
    report=a.artifacts/"reports"/"flujo_reportes_historicos_api.json"; audit=[]
    if a.resume and report.is_file(): audit=json.loads(report.read_text(encoding="utf-8"))
    completed={item["lote"] for item in audit}; api=Api(a.base_url,a.email,a.password)
    for batch, samples in sorted(by_batch.items()):
        if batch in completed:
            continue
        batch_data=api.get(f"lubrication/sample-batches/{batch}/")
        if batch_data.get("estado") == "reportado":
            audit.append({"lote":batch,"muestras":len(samples),"reportes":"preexistentes","visible_cliente":False,"aprobados":False})
            report.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            continue
        state=batch_data.get("estado")
        if state not in {"revisado", "reportado"}:
            api.post(f"lubrication/result-entry/batches/{batch}/confirm-all/", {"allow_incomplete_historical": True})
            api.post(f"lubrication/review-results/batches/{batch}/complete/", {"observaciones":"Revisión histórica automática: datos importados y pendientes de validación funcional."})
        for item in samples:
            row=source[item["oa"]]; conclusion=str(row.get("CONCLUSIÓN") or "").strip() or "Sin conclusión histórica disponible. Requiere revisión técnica."
            api.post(f"lubrication/interpretation/samples/{item['muestra']}/", {
                "conclusion": conclusion,
                "comentarios_predefinidos": [], "comentarios_manuales": [],
                "graficas_activas": False, "graficas_seleccionadas": [],
                "motivo": "Interpretación histórica importada; requiere validación técnica antes de aprobación.",
            })
        result=api.post("lubrication/reports/generate-batch-from-interpretation/", {"lote":batch,"responsable":"Global Oil - migración histórica"})
        audit.append({"lote":batch,"muestras":len(samples),"reportes":result.get("generated",0),"visible_cliente":False,"aprobados":False})
        report.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary.update({"mode":"apply","writes":True,"reports_generated":sum(x["reportes"] for x in audit),"report":str(report)});print(json.dumps(summary,ensure_ascii=False))
if __name__=="__main__":main()

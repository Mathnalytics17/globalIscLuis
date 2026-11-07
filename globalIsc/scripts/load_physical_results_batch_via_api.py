#!/usr/bin/env python3
"""Fill and submit the official result-entry Excel template once per batch.

The workbook comes from the API immediately before upload, retaining its token
and field keys.  This is a bulk transport optimization, not a database bypass.
"""
import argparse, json
from collections import defaultdict
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from load_global_oil_via_api import Api


def jsonl(path): return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()]


def main():
    p=argparse.ArgumentParser(description="Carga resultados físicos con la plantilla oficial API por lote.")
    p.add_argument("--artifacts",type=Path,default=Path("outputs/migracion_historica_global_oil"));p.add_argument("--base-url",default="http://localhost:8000")
    p.add_argument("--email");p.add_argument("--password");p.add_argument("--apply",action="store_true");p.add_argument("--limit",type=int);p.add_argument("--resume",action="store_true");p.add_argument("--test-code")
    p.add_argument("--payload-file", default="api_result_payloads_physical.jsonl", help="Archivo JSONL de resultados en staging.")
    p.add_argument("--report-file", default="carga_api_resultados_fisicos.json", help="Nombre del reporte de progreso en reports.")
    p.add_argument("--completed-report", help="Reporte adicional cuyos lotes ya se consideran terminados.")
    p.add_argument("--batch-shard-count", type=int, default=1, help="Particiones deterministas de lotes para reanudar en paralelo.")
    p.add_argument("--batch-shard-index", type=int, default=0, help="Índice de partición, desde cero.")
    a=p.parse_args(); imported=json.loads((a.artifacts/"reports"/"carga_api_muestras.json").read_text(encoding="utf-8")); mapping=json.loads((a.artifacts/"staging"/"oa_pruebas_muestra.json").read_text(encoding="utf-8")); payloads=jsonl(a.artifacts/"staging"/a.payload_file)
    batch_for_oa={str(row["oa"]):row["lote"] for row in imported}; values_by_test=defaultdict(list)
    # Rows rejected at sample intake have no mapping and therefore must never
    # enter the official result-entry workbook.
    payloads = [row for row in payloads if str(row["oa"]) in mapping and row["test_code"] in mapping[str(row["oa"])]]
    for row in payloads:
        if a.test_code and row["test_code"] != a.test_code: continue
        test_id=mapping[str(row["oa"])][row["test_code"]]
        values_by_test[str(test_id)].extend(row["values"])
    tests_by_batch=defaultdict(set)
    for oa,batch in batch_for_oa.items():
        for test_id in mapping.get(oa,{}).values():
            if str(test_id) in values_by_test: tests_by_batch[batch].add(str(test_id))
    report_path=a.artifacts/"reports"/a.report_file; prior=[]
    if a.resume and report_path.is_file(): prior=json.loads(report_path.read_text(encoding="utf-8"))
    if a.batch_shard_count < 1 or not 0 <= a.batch_shard_index < a.batch_shard_count:
        p.error("--batch-shard-index debe estar entre 0 y --batch-shard-count - 1")
    completed={row["lote"] for row in prior}
    if a.completed_report:
        completed_path=a.artifacts/"reports"/a.completed_report
        if completed_path.is_file():
            completed.update(row["lote"] for row in json.loads(completed_path.read_text(encoding="utf-8")))
    pending=[batch for batch in sorted(tests_by_batch) if batch not in completed]
    batches=[batch for index,batch in enumerate(pending) if index % a.batch_shard_count == a.batch_shard_index]
    if a.limit: batches=batches[:a.limit]
    summary={"mode":"dry_run","batches":len(batches),"values":sum(len(tests_by_batch[x]) for x in batches),"writes":False}
    if not a.apply: print(json.dumps(summary,ensure_ascii=False));return
    if not a.email or not a.password:p.error("--email y --password son obligatorios con --apply")
    api=Api(a.base_url,a.email,a.password); audit=list(prior)
    for batch in batches:
        template=api._request("get","lubrication/result-entry/excel/template/",params={"lote":batch,"modo":"consolidado"})
        template.raise_for_status(); workbook=load_workbook(BytesIO(template.content))
        updated=0
        for sheet in workbook.worksheets:
            if sheet.title in {"Metadata","_LISTAS","Instrucciones"}: continue
            headers={cell.value:index+1 for index,cell in enumerate(sheet[1]) if cell.value}
            if not {"PruebaMuestraID","Valor"}.issubset(headers): continue
            for row in range(2,sheet.max_row+1):
                test_id=str(sheet.cell(row,headers["PruebaMuestraID"]).value or "")
                component=str(sheet.cell(row,headers.get("Componente", 1)).value or "")
                if test_id in tests_by_batch[batch] and test_id in values_by_test:
                    matches=[value for value in values_by_test[test_id] if str(value.get("component_code") or "") == component]
                    if matches:
                        sheet.cell(row,headers["Valor"]).value=str(matches[0]["value"]); updated+=1
        output=BytesIO();workbook.save(output)
        response=api.post_file("lubrication/result-entry/excel/import/",f"{batch}_fisicos.xlsx",output.getvalue())
        if response.get("rows_imported") != updated: raise RuntimeError(f"{batch}: importó {response.get('rows_imported')} de {updated} filas")
        audit.append({"lote":batch,"values":updated,"tests":response.get("tests_updated"),"rows":response.get("rows_imported")})
        # Make a completed batch durable immediately.  If Docker/Desktop is
        # stopped midway through a long import, --resume will continue with
        # the next official batch template instead of importing this one again.
        report_path.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    report_path.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    summary.update({"mode":"apply","writes":True,"completed_batches":len(audit),"values":sum(x["values"] for x in audit)});print(json.dumps(summary,ensure_ascii=False))
if __name__=="__main__":main()

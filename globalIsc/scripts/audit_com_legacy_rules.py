#!/usr/bin/env python3
"""Audit source COM_* conclusions against deterministic ETL rules.

COM columns are evidence only: discrepancies are written for analyst review and
never mutate imported results or current technical configurations.
"""
import argparse, csv, json, re
from pathlib import Path

RULES = (
    ("Apariencia", "COM_Apariencia", lambda value: str(value).strip().upper() in {"CARACTERÍSTICA", "CARACTERISTICA"}),
    ("Olor", "COM_Olor", lambda value: str(value).strip().upper() in {"CARACTERÍSTICO", "CARACTERISTICO"}),
    ("Hollín", "COM_Hollín", lambda value: numeric(value) is not None and numeric(value) < 2),
    ("TBN", "COM_TBN", lambda value: numeric(value) is not None and numeric(value) >= 4),
    ("Agua", "COM_Agua", lambda value: numeric(value) is not None and numeric(value) < 500),
)

def numeric(value):
    text=str(value or "").strip().replace(",", ".")
    if text.startswith("<"): text=text[1:]
    try: return float(text)
    except ValueError: return None
def normal(value):
    text=str(value or "").strip().upper()
    return "NORMAL" in text and "NO DESEADO" not in text
def main():
    parser=argparse.ArgumentParser(description="Contrasta COM_* histórico contra reglas determinísticas.")
    parser.add_argument("--artifacts",type=Path,default=Path("outputs/migracion_historica_global_oil"));args=parser.parse_args()
    source=args.artifacts/"staging"/"reportes_oa_raw.jsonl"; detail=[]; summary=[]
    rows=[json.loads(line)["data"] for line in source.open(encoding="utf-8") if line.strip()]
    for column,com_column,evaluate in RULES:
        checked=matches=0
        for row in rows:
            legacy=row.get(com_column)
            if not str(legacy or "").strip() or row.get(column) in (None,""): continue
            expected=evaluate(row[column]); checked+=1; ok=(normal(legacy)==expected)
            matches+=ok
            if not ok: detail.append({"oa":row.get("OA"),"prueba":column,"resultado":row[column],"com_historico":legacy,"esperado_regla_actual":"NORMAL" if expected else "NO_DESEADO"})
        summary.append({"prueba":column,"evaluados":checked,"coinciden":matches,"difieren":checked-matches})
    reports=args.artifacts/"reports"; reports.mkdir(parents=True,exist_ok=True)
    with (reports/"auditoria_com_reglas_detalle.csv").open("w",newline="",encoding="utf-8-sig") as out:
        writer=csv.DictWriter(out,fieldnames=["oa","prueba","resultado","com_historico","esperado_regla_actual"]);writer.writeheader();writer.writerows(detail)
    (reports/"auditoria_com_reglas.json").write_text(json.dumps({"summary":summary,"differences":len(detail),"scope":"Reglas determinísticas; COM no modifica límites."},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"rules":len(RULES),"differences":len(detail),"report":str(reports/"auditoria_com_reglas.json")},ensure_ascii=False))
if __name__=="__main__":main()

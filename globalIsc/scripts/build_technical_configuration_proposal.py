#!/usr/bin/env python3
"""Build a reviewable technical-configuration proposal from approved sheets only.

Included sources: 01 metal limits, 02 viscosity, 03 degradation and 05 ISO4406.
Explicitly excluded: 06 metal origins, 07 repertoire and 10 technical notes.
This stage never writes to the application database or calls an API.
"""
import argparse
import csv
import json
from pathlib import Path


INCLUDED = ("01_limites_metales.csv", "02_viscosidad.csv", "03_degradacion.csv", "05_iso4406.csv")
EXCLUDED = ("06_origenes_metales.csv", "07_repertorio.csv", "10_notas_tecnicas.csv")


def read(path):
    return list(csv.DictReader(path.open(encoding="utf-8-sig")))


def text(value): return str(value or "").strip()


def number(value):
    try: return float(text(value).replace(",", "."))
    except ValueError: return None


def main():
    p=argparse.ArgumentParser(description="Genera propuesta ETL de catálogos y límites técnicos Global Oil.")
    p.add_argument("--artifacts",type=Path,default=Path("outputs/migracion_historica_global_oil"));a=p.parse_args()
    source=a.artifacts/"catalogos_fuente"
    missing=[name for name in INCLUDED if not (source/name).is_file()]
    if missing: p.error(f"Faltan extracciones aprobadas: {missing}")
    metals, viscosity, degradation, iso = (read(source/name) for name in INCLUDED)

    iso_items=[]; iso_rules=[]
    for row in iso[3:]:
        code=text(row["col_1"])
        if not code: continue
        values={"4um":number(row["col_5"]),"6um":number(row["col_6"]),"14um":number(row["col_7"])}
        iso_items.append({"codigo":code,"nombre":code,"atributos":{"tipo_sistema_uso":text(row["col_2"]),"componentes_tipicos":text(row["col_3"]),"sensibilidad":text(row["col_4"]),**values}})
        iso_rules.append({"criterio_catalogo":"NIVEL_CONTAMINACION","criterio_item":code,"prueba":"NIVEL_CONTAMINACION","operador":"max","campos":{"4um":values["4um"],"6um":values["6um"],"14um":values["14um"]},"semaforo":False})

    grades=[]
    for row in viscosity[3:]:
        grade=text(row["col_2"])
        if grade:
            grades.append({"codigo":grade,"nombre":grade,"atributos":{"familia":text(row["col_1"]),"vmin":number(row["col_3"]),"vmax":number(row["col_4"]),"iv_mono":number(row["col_5"]),"iv_multi":number(row["col_6"]),"notas":text(row["col_7"])}})

    # The performance matrix begins after the degradation rules.  Preserve
    # every source value in a dedicated catalog; conversion to component limits
    # is deliberately a later stage because the laboratory must confirm which
    # side of an "EI/FI" pair is represented by values such as "10/0".
    performance=[]
    for row in degradation[19:]:
        specification=text(row["col_1"])
        if specification:
            performance.append({
                "codigo":specification,
                "nombre":specification,
                "atributos":{
                    "espuma_seq_i":text(row["col_2"]),
                    "espuma_seq_ii":text(row["col_3"]),
                    "espuma_seq_iii":text(row["col_4"]),
                    "punto_chispa_min":number(row["col_5"]),
                },
            })

    systems=[]; metal_rules=[]
    headers=metals[2]
    for column in range(4,14):
        key=f"col_{column}"; system=text(headers[key])
        if system: systems.append({"codigo":system.upper().replace(" ","_"),"nombre":system})
    for row in metals[3:]:
        metal=text(row["col_1"])
        if not metal: continue
        for column in range(4,14):
            value=text(row[f"col_{column}"])
            if value and value != "*":
                metal_rules.append({"criterio_catalogo":"TIPO_SISTEMA_USO","criterio_item":text(headers[f"col_{column}"]),"prueba":"ELEMENTOS","campo":metal,"operador":"max","max_critico":number(value),"semaforo":True,"clase":text(row["col_3"])})

    internal_rules=[]
    for row in degradation[3:]:
        parameter=text(row["col_1"])
        if parameter:
            internal_rules.append({"parametro":parameter,"metodo":text(row["col_2"]),"aplica_a":text(row["col_3"]),"criterio_fuente":text(row["col_4"]),"interpretacion_fuente":text(row["col_5"]),"tipo":"REGLA_INTERNA_O_TENDENCIA"})

    proposal={
        "sources":{"included":list(INCLUDED),"excluded":list(EXCLUDED)},
        "catalogos":[
            {"codigo":"NIVEL_CONTAMINACION","items":iso_items},
            {"codigo":"GRADO_VISCOSIDAD","items":grades},
            {"codigo":"TIPO_SISTEMA_USO","items":systems},
            {"codigo":"NIVEL_DESEMPENO","items":performance},
        ],
        "pruebas_compuestas":[
            {"codigo":"NIVEL_CONTAMINACION","resultados":["ISO 4406"],"componentes":["4um","6um","14um"]},
            {"codigo":"ELEMENTOS","resultado":"Elementos","componentes":"metales"},
        ],
        "limites_catalogo":{"iso4406_eq":iso_rules,"metales_por_sistema":metal_rules},
        "limites_por_grado":[
            {"prueba":"VISCOSIDAD_100C","criterio_catalogo":"GRADO_VISCOSIDAD","operador":"between","min_atributo":"vmin","max_atributo":"vmax","semaforo":True},
            {"prueba":"INDICE_VISCOSIDAD","criterio_catalogo":"GRADO_VISCOSIDAD","regla":"iv_mono_o_iv_multi_segun_familia","semaforo":True},
        ],
        "reglas_internas":internal_rules,
        "com_legacy":{"uso":"validación retrospectiva de la propuesta; no origen autónomo de límite","campos":"COM_<prueba>"},
    }
    output=a.artifacts/"homologacion"/"propuesta_configuracion_tecnica.json";output.write_text(json.dumps(proposal,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"catalogos":len(proposal["catalogos"]),"iso_max_rules":len(iso_rules),"metal_rules":len(metal_rules),"performance_items":len(performance),"internal_rules":len(internal_rules),"output":str(output)},ensure_ascii=False))

if __name__=="__main__":main()

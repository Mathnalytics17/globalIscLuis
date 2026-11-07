#!/usr/bin/env python3
"""Materialize ELEMENTOS limits by system through the public API."""
import argparse, json, re, unicodedata
from pathlib import Path
from load_global_oil_via_api import Api

def one(rows, fn, label):
    found=[x for x in rows if fn(x)]
    if len(found)!=1: raise RuntimeError(f"{label}: {len(found)} registros")
    return found[0]

def field_code(*parts):
    """Mirror the backend's canonical key for a result/component field."""
    normalized=[]
    for part in parts:
        ascii_value=unicodedata.normalize('NFKD',str(part)).encode('ascii','ignore').decode('ascii').lower()
        normalized.append(re.sub(r'[^a-z0-9]+','_',ascii_value).strip('_'))
    return '_'.join(part for part in normalized if part)

def main():
    p=argparse.ArgumentParser(description="Carga límites de ELEMENTOS por tipo de sistema.")
    p.add_argument('--artifacts',type=Path,default=Path('outputs/migracion_historica_global_oil'));p.add_argument('--base-url',default='http://localhost:8000');p.add_argument('--email');p.add_argument('--password');p.add_argument('--apply',action='store_true');a=p.parse_args()
    proposal=json.loads((a.artifacts/'homologacion'/'propuesta_configuracion_tecnica.json').read_text(encoding='utf-8'))
    rules=proposal['limites_catalogo']['metales_por_sistema']
    if not a.apply:
        print(json.dumps({'mode':'dry_run','test':'ELEMENTOS','systems':10,'configured_max_rules':len(rules),'writes':False},ensure_ascii=False));return
    if not a.email or not a.password:p.error('--email y --password son obligatorios con --apply')
    api=Api(a.base_url,a.email,a.password)
    test=one(api.get('lubrication/tests/',{'search':'ELEMENTOS','include_structure':'true','page_size':100}),lambda x:x.get('acronimo')=='ELEMENTOS','Prueba ELEMENTOS')
    catalog=one(api.get('technical-config/catalogs/',{'search':'tipo_sistema_uso'}),lambda x:x.get('codigo')=='tipo_sistema_uso','Catálogo sistema')
    sample_field=one(api.get('technical-config/sample-fields/',{'search':'tipo_sistema_uso'}),lambda x:x.get('codigo')=='tipo_sistema_uso','Campo técnico sistema')
    leaves=[]
    for r in test['resultados']:
        for d in r['divisiones']:
            for c in d['componentes']:
                leaves.append({'codigo':field_code(r['nombre'],c['nombre']),'nombre':f'Elementos {c["acronimo"]}','resultado':r['id'],'division':d['id'],'componente':c['id'],'unidad':'ppm'})
    leaves_by_metal={leaf['nombre'].rsplit(' ',1)[-1].upper():leaf for leaf in leaves}
    item_by_name={item['nombre'].casefold():item for item in catalog['items']}
    by_system={}
    for rule in rules:
        item=item_by_name.get(rule['criterio_item'].casefold())
        leaf=leaves_by_metal.get(rule['campo'].upper())
        # The source supplies a single condemnatory ceiling, not a warning
        # band.  Map it as the operative maximum and keep yellow disabled.
        if item and leaf: by_system.setdefault(item['id'],{})[leaf['codigo']]={'operador':'max','max_aceptable':str(rule['max_critico']),'usar_amarillo':False}
    criteria=[]
    for item in catalog['items']:
        criteria.append({'nombre':item['nombre'],'codigo':f'sistema_{item["codigo"]}','tipo_criterio':'catalogo_item','catalogo_item':item['id'],'valor':item['nombre'],'valores':by_system.get(item['id'],{}),'selecciones_catalogo':[{'catalogo':catalog['id'],'item':item['id']}]})
    payload={'prueba':test['id'],'fuente':'catalogos','catalogos':[{'catalogo':catalog['id'],'campo_tecnico_muestra':sample_field['id']}],'modo_seleccion':'desde_muestra_editable','publicar':True,'decision':{'nombre':'Metales por sistema','campos':[]},'campos':[{**leaf,'origen_limite':'catalogo','operador':'max','tipo_comparacion':'numerica','participa':True,'evalua':True} for leaf in leaves],'criterios':criteria}
    out=api.post('technical-config/limit-sources/configure/',payload)
    report=a.artifacts/'reports'/'configuracion_limites_elementos_api.json';report.write_text(json.dumps({'response':out,'rule_count':len(rules)},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'mode':'apply','source_id':out['id'],'version':out['version'],'criteria':len(criteria),'fields':len(leaves),'configured_max_rules':len(rules),'report':str(report)},ensure_ascii=False))
if __name__=='__main__':main()

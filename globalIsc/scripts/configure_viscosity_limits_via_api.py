#!/usr/bin/env python3
"""Create VISCOSIDAD_100C ranges conditional on Grado de viscosidad."""
import argparse,json,re,unicodedata
from pathlib import Path
from load_global_oil_via_api import Api
def one(rows,fn,label):
 x=[r for r in rows if fn(r)]
 if len(x)!=1:raise RuntimeError(f'{label}: {len(x)} registros')
 return x[0]
def field_code(*parts):
 """Mirror the backend's canonical key for a result/component field."""
 normalized=[]
 for part in parts:
  ascii_value=unicodedata.normalize('NFKD',str(part)).encode('ascii','ignore').decode('ascii').lower()
  normalized.append(re.sub(r'[^a-z0-9]+','_',ascii_value).strip('_'))
 return '_'.join(part for part in normalized if part)
def main():
 p=argparse.ArgumentParser(description='Carga rangos VMIN/VMAX por grado.');p.add_argument('--artifacts',type=Path,default=Path('outputs/migracion_historica_global_oil'));p.add_argument('--base-url',default='http://localhost:8000');p.add_argument('--email');p.add_argument('--password');p.add_argument('--apply',action='store_true');a=p.parse_args()
 if not a.apply:print(json.dumps({'mode':'dry_run','test':'VISCOSIDAD_100C','catalog':'GRADO_VISCOSIDAD','rule':'between','writes':False},ensure_ascii=False));return
 if not a.email or not a.password:p.error('--email y --password son obligatorios con --apply')
 api=Api(a.base_url,a.email,a.password)
 test=one(api.get('lubrication/tests/',{'search':'VISCOSIDAD_100C','include_structure':'true','page_size':100}),lambda x:x.get('acronimo')=='VISCOSIDAD_100C','Prueba viscosidad')
 cat=one(api.get('technical-config/catalogs/',{'search':'grado_viscosidad'}),lambda x:x.get('codigo')=='grado_viscosidad','Catálogo grado')
 field=one(api.get('technical-config/sample-fields/',{'search':'grado_viscosidad'}),lambda x:x.get('codigo')=='grado_viscosidad','Campo grado')
 r=test['resultados'][0];d=r['divisiones'][0];c=d['componentes'][0];leaf={'codigo':field_code(r['nombre'],c['nombre']),'nombre':test['nombre_variable'],'resultado':r['id'],'division':d['id'],'componente':c['id'],'unidad':'cSt'}
 criteria=[]
 for item in cat['items']:
  values={x['campo_info']['codigo']:x['valor'] for x in item['valores']}
  if not values.get('vmin'):continue
  rule={'operador':'between','min_aceptable':values['vmin'],'max_aceptable':values.get('vmax') or None,'usar_amarillo':False}
  if not rule['max_aceptable']:
   # The source's "solo VMIN" grades are intentionally a lower-bound rule.
   rule={'operador':'min','min_aceptable':values['vmin'],'usar_amarillo':False}
  criteria.append({'nombre':item['nombre'],'codigo':f'grado_{item["codigo"]}','tipo_criterio':'catalogo_item','catalogo_item':item['id'],'valor':item['nombre'],'valores':{leaf['codigo']:rule},'selecciones_catalogo':[{'catalogo':cat['id'],'item':item['id']}]})
 payload={'prueba':test['id'],'fuente':'catalogos','catalogos':[{'catalogo':cat['id'],'campo_tecnico_muestra':field['id']}],'modo_seleccion':'desde_muestra_editable','publicar':True,'decision':{'nombre':'Viscosidad por grado','campos':[]},'campos':[{**leaf,'origen_limite':'catalogo','operador':'between','tipo_comparacion':'numerica','participa':True,'evalua':True}],'criterios':criteria}
 out=api.post('technical-config/limit-sources/configure/',payload);report=a.artifacts/'reports'/'configuracion_limites_viscosidad_api.json';report.write_text(json.dumps({'response':out,'criteria':criteria},ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'mode':'apply','source_id':out['id'],'version':out['version'],'criteria':len(criteria),'rule':'between','report':str(report)},ensure_ascii=False))
if __name__=='__main__':main()

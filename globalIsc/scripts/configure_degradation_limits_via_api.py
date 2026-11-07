#!/usr/bin/env python3
"""Create direct, source-backed degradation limits via the public API."""
import argparse,json,re,unicodedata
from pathlib import Path
from load_global_oil_via_api import Api

RULES={
 'APARIENCIA':('eq',{'operador':'eq','valor_esperado':'CARACTERÍSTICA','usar_amarillo':False}),
 'OLOR':('eq',{'operador':'eq','valor_esperado':'CARACTERÍSTICO','usar_amarillo':False}),
 'HOLLIN':('max',{'operador':'max','max_aceptable':'2','usar_amarillo':False}),
 'AGUA':('max',{'operador':'max','max_aceptable':'500','usar_amarillo':False}),
 'TBN':('min',{'operador':'min','min_critico':'4','min_aceptable':'5','usar_amarillo':True}),
}
def one(rows,code):
 x=[r for r in rows if r.get('acronimo')==code]
 if len(x)!=1:raise RuntimeError(f'{code}: {len(x)} pruebas')
 return x[0]
def field_code(*parts):
 """Generate the same result key consumed by the limit configuration UI."""
 normalized=[]
 for part in parts:
  ascii_value=unicodedata.normalize('NFKD',str(part)).encode('ascii','ignore').decode('ascii').lower()
  normalized.append(re.sub(r'[^a-z0-9]+','_',ascii_value).strip('_'))
 return '_'.join(part for part in normalized if part)
def main():
 p=argparse.ArgumentParser(description='Carga límites explícitos de degradación.');p.add_argument('--artifacts',type=Path,default=Path('outputs/migracion_historica_global_oil'));p.add_argument('--base-url',default='http://localhost:8000');p.add_argument('--email');p.add_argument('--password');p.add_argument('--apply',action='store_true');a=p.parse_args()
 if not a.apply:print(json.dumps({'mode':'dry_run','tests':list(RULES),'informativos':['NITRACION','OXIDACION','SULFATACION','DENSIDAD_15C'],'writes':False},ensure_ascii=False));return
 if not a.email or not a.password:p.error('--email y --password son obligatorios con --apply')
 api=Api(a.base_url,a.email,a.password); created=[]
 for code,(operator,rule) in RULES.items():
  test=one(api.get('lubrication/tests/',{'search':code,'include_structure':'true','page_size':100}),code)
  leaves=[]
  for r in test['resultados']:
   for d in r['divisiones']:
    for c in d['componentes']:leaves.append({'codigo':field_code(r['nombre'],c['nombre']),'nombre':test['nombre_variable'],'resultado':r['id'],'division':d['id'],'componente':c['id'],'unidad':r.get('unidad_medida') or ''})
  payload={'prueba':test['id'],'fuente':'global','modo_seleccion':'fijo','publicar':True,'decision':{'nombre':f'Regla técnica {code}','campos':[]},'campos':[{**leaf,'origen_limite':'directo','operador':operator,'tipo_comparacion':'numerica' if code not in {'APARIENCIA','OLOR'} else 'informativo','participa':True,'evalua':True,'valor_global':rule} for leaf in leaves],'criterios':[]}
  result=api.post('technical-config/limit-sources/configure/',payload);created.append({'test':code,'source':result['id'],'version':result['version']})
 out=a.artifacts/'reports'/'configuracion_limites_degradacion_api.json';out.write_text(json.dumps(created,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'mode':'apply','configured':created,'report':str(out)},ensure_ascii=False))
if __name__=='__main__':main()

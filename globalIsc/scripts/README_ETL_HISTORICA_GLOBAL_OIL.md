# ETL histórica Global Oil

`etl_historica_global_oil.py` implementa la primera etapa de la ETL: extracción, normalización y generación de colas de homologación. No importa datos a Django y no abre conexión a PostgreSQL.

## Ejecutar en Windows

Desde `backend\globalIsc`:

```powershell
python scripts/etl_historica_global_oil.py `
  --reportes "C:\Users\Usuario\Downloads\REGISTRO OA.xlsx" `
  --reportes "C:\Users\Usuario\Downloads\REPORTES 2026 CORTO 20 SEPTIMBRE (1).xlsx" `
  --conocimiento "C:\Users\Usuario\Downloads\Base_Conocimiento_Aceites_v9.xlsx" `
  --output "outputs\migracion_historica_global_oil" --replace
```

`--reportes` se puede repetir. Cada archivo queda identificado en los
artefactos y la clave de migración es `archivo:OA`; así, una OA reutilizada en
dos entregas no sobrescribe ni omite una muestra. El valor original sigue
guardado como `OA_ORIGINAL` y en los campos adicionales de la muestra.

También puede ejecutar desde `backend\globalIsc\scripts`:

```powershell
.\run_etl_historica_global_oil.ps1 -Replace
```

## Carga completa: todos o solo Mineros Aluvial

`run_final_global_oil_etl.ps1` prepara el artefacto, reconstruye la estructura
por API y carga los resultados. Tiene dos alcances:

- `-ClientScope all`: conserva todos los clientes de la fuente.
- `-ClientScope mineros`: conserva únicamente **Mineros Aluvial S.A.S.** y
  **Mineros Aluvial S.A.S. BIC**, y los unifica como `MINEROS ALUVIAL S.A.S.`.

El reinicio solo ocurre cuando se indican **ambos** `-Apply` y `-ResetLocal`.
Ejecute esto únicamente contra la base local; el script pedirá la contraseña
oculta si no la recibe como parámetro.

```powershell
# Vista previa: no borra ni escribe datos.
.\scripts\run_final_global_oil_etl.ps1 -ClientScope mineros

# Reinicio local e importación desde cero, solo para Mineros Aluvial.
.\scripts\run_final_global_oil_etl.ps1 -ClientScope mineros -Apply -ResetLocal -SkipFinalVerification

# Reinicio local e importación desde cero, para todos los clientes.
.\scripts\run_final_global_oil_etl.ps1 -ClientScope all -Apply -ResetLocal -SkipFinalVerification
```

El flujo de reportes se ejecuta al final y genera borradores internos; no los
aprueba, publica ni envía por correo.

## Artefactos generados

- `staging/reportes_oa_raw.jsonl`: conservación íntegra de cada fila de la fuente.
- `staging/muestras.csv`, `mediciones.csv`, `interpretaciones.jsonl`: entidades largas y preparadas para validación.
- `homologacion/*.csv`: listas editables de clientes, equipos, placas, lubricantes, tipos, viscosidades, especificaciones, responsables y pruebas.
- `catalogos_fuente/*.csv`: extracción física de cada hoja de la base técnica.
- `qa/*.csv`: duplicados y advertencias que requieren decisión.
- `reports/manifest.json` y `reporte_ejecucion.md`: control de huellas, conteos y resultado de la ejecución.

## Flujo API reproducible

Una vez aprobada la homologación de activos, estas etapas escriben exclusivamente
por la API local (nunca con ORM). Todas admiten una primera ejecución sin
`--apply` para revisar conteos.

```powershell
# Desde backend\globalIsc; use las credenciales locales por variables de entorno.
python scripts/etl_global_oil_domain.py --artifacts outputs/migracion_historica_global_oil
python scripts/build_api_result_payloads.py --artifacts outputs/migracion_historica_global_oil
python scripts/build_physical_result_payloads.py --artifacts outputs/migracion_historica_global_oil
python scripts/load_global_oil_via_api.py --artifacts outputs/migracion_historica_global_oil --apply --email <correo> --password <clave>
python scripts/load_compound_tests_via_api.py --apply --email <correo> --password <clave>
python scripts/load_physical_tests_via_api.py --apply --email <correo> --password <clave>
python scripts/load_historic_samples_via_api.py --artifacts outputs/migracion_historica_global_oil --apply --email <correo> --password <clave>
python scripts/advance_compound_workflow_via_api.py --artifacts outputs/migracion_historica_global_oil --apply --email <correo> --password <clave>
python scripts/assign_physical_tests_via_api.py --artifacts outputs/migracion_historica_global_oil --apply --email <correo> --password <clave>
```

`<1` se interpreta como no detección: no se carga como resultado ni se
convierte a `1`. La regla vive en `etl_global_oil_domain.py`, por lo que una
ejecución nueva conserva exactamente el mismo criterio.

Los resultados se guardan inicialmente como borrador a través de
`submit_compound_results_via_api.py`; la confirmación, revisión y publicación
siguen siendo pasos separados. Los límites permanecen desactivados hasta que
las matrices de la base técnica se conviertan en versiones de límite aprobadas.

La fase posterior de aplicación deberá rechazar cualquier fila con homologación distinta de `APROBADO`, conservar el OA original y registrar la ejecución en `CorridaImportacion`.

## Propuestas contra el catálogo local

Después de ejecutar la extracción, genere propuestas de coincidencia sin escribir en la base:

```powershell
docker compose -p globaloil-local --env-file .env.local -f docker-compose.prod.yml -f docker-compose.local.yml exec -T web python scripts/homologacion_asistida_global_oil.py
```

El resultado queda en `outputs/migracion_historica_global_oil/homologacion/propuestas_db_local/`. Una coincidencia exacta es una propuesta, no una aprobación automática.

## Reinicio de la base local para datos reales

El siguiente comando elimina toda la información de negocio local, incluidas las empresas, y conserva usuarios, roles y permisos RBAC. No use este comando contra una base remota.

```powershell
docker compose -p globaloil-local --env-file .env.local -f docker-compose.prod.yml -f docker-compose.local.yml exec -T web python manage.py reset_to_security_baseline --dry-run
docker compose -p globaloil-local --env-file .env.local -f docker-compose.prod.yml -f docker-compose.local.yml exec -T web python manage.py reset_to_security_baseline --yes
```

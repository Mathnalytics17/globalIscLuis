# 07. ETL y homologación asistida

## Alcance implementado

La ETL actual tiene dos pasos ejecutables y reproducibles:

1. `etl_historica_global_oil.py`: extrae ambos Excel, conserva la fuente íntegra, normaliza muestras, mediciones e interpretaciones, y genera listas de homologación.
2. `homologacion_asistida_global_oil.py`: consulta el catálogo local en modo de solo lectura y genera propuestas de coincidencia. No modifica Django ni PostgreSQL.

Los artefactos locales se escriben en `globalIsc/outputs/migracion_historica_global_oil/`, fuera de Git. El manifiesto conserva las huellas SHA-256 de los dos archivos de entrada.

## Línea base local

El entorno local se reinició con `reset_to_global_oil_baseline`. Se preservan únicamente la empresa interna **Global Oil**, el administrador `admin@globaloil.local` y el modelo de seguridad RBAC. No quedan empresas cliente, usuarios externos, activos, catálogos, muestras, pruebas, resultados ni información demo. Esta limpieza no toca los Excel ni los artefactos ETL físicos.

## Resultado de la primera comparación local

| Dominio | Valores fuente | Coincidencias exactas locales | Decisión |
|---|---:|---:|---|
| Empresas | 27 | 0 | Proponer creación controlada; no vincular a empresas demo. |
| Contextos empresa/equipo | 205 | 0 | Crear después de aprobar empresa destino. |
| Lubricantes | 117 | 0 | Proponer catálogo global nuevo o aprobar equivalencias. |
| Pruebas | 42 | 0 | Crear catálogo de pruebas y unidades antes de resultados. |

La ausencia de coincidencias es esperable: la base local contiene datos de demostración, no el maestro histórico de Global Oil. Una coincidencia exacta futura seguirá siendo una propuesta, no una aprobación automática.

## Trabajo pendiente antes del piloto

1. Revisar `homologacion/propuestas_db_local/*.csv` y completar `decision`, `status` y, cuando aplique, `candidate_id`.
2. Definir los maestros que se crearán: empresa, máquina, lubricante, catálogo técnico y prueba.
3. Definir el modelo de OA externo, placa y punto de muestreo antes de insertar muestras.
4. Aprobar las 42 pruebas con unidad y política de límite; mantener los valores cualificados (`<1`, `>x`) como texto y operador.
5. Seleccionar diez OA representativas para el piloto, incluyendo al menos un valor cualificado, comentario y período no estándar.

## Criterio para habilitar el cargador piloto

El cargador a Django se habilita únicamente cuando cada fila del piloto tenga maestros aprobados, OA único, fecha válida, prueba homologada y ninguna advertencia abierta. Debe crear una `CorridaImportacion` reversible y registrar los identificadores creados para poder conciliar y revertir el piloto.

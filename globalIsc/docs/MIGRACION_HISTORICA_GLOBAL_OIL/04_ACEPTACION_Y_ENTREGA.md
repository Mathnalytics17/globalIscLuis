# Aceptacion y entrega final

## Conciliacion obligatoria

El informe final debe separar, para cada fuente y ejecucion:

| Medida | Definicion |
| --- | --- |
| Registros recibidos | Filas de la fuente dentro del alcance aprobado. |
| Registros leidos | Filas que el proceso pudo interpretar estructuralmente. |
| Registros cargados | Filas que crearon o actualizaron relaciones de destino validas. |
| Registros con advertencia | Filas cargadas que conservan una limitacion no bloqueante. |
| Registros en cuarentena | Filas no cargadas por una decision pendiente o inconsistencia relevante. |
| Registros rechazados | Filas excluidas por regla bloqueante aprobada. |
| Duplicados evitados | Registros detectados por llave externa y no insertados nuevamente. |

La igualdad esperada es:

`recibidos = cargados + cargados con advertencia + cuarentena + rechazados`

Toda diferencia debe explicarse con identificadores de OA.

## Paquete de entrega

1. Codigo fuente y dependencias necesarias para reproducir los procesos.
2. Matriz final de homologacion y catalogos aprobados.
3. Bitacoras de ejecucion y reporte de excepciones.
4. Resultado de la carga y conciliacion.
5. Informe de validacion con muestra tecnica revisada.
6. Instrucciones locales de instalacion, ejecucion, respaldo y recuperacion.
7. Acta de entrega con pendientes, si los hubiera.

## Criterios de aceptacion

- La ejecucion local se puede repetir con las fuentes aprobadas.
- No se altera el archivo original.
- No se duplican OAs al reintentar una carga.
- Las relaciones cargadas son validas y consultables en la plataforma.
- Las excepciones son visibles y trazables.
- La conciliacion tiene resultado explicable.
- DATAIA recibe el codigo, documentos y evidencias de prueba.

## Proceso de aceptacion

1. Se entrega el paquete junto con el informe de validacion.
2. DATAIA dispone de cinco dias habiles para observaciones tecnicas especificas.
3. Se corrigen las observaciones reproducibles dentro del alcance.
4. DATAIA comunica aceptacion por escrito o mediante acta.
5. Desde la aceptacion inicia la garantia tecnica de treinta dias para defectos reproducibles atribuibles a los procesos entregados.

## Fuera de garantia

No se consideran defectos de la migracion las nuevas fuentes, cambios funcionales o arquitectonicos, modificaciones posteriores de requisitos, ni inconsistencias historicas que no puedan resolverse con datos y reglas aprobadas.

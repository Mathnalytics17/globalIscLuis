# Migracion historica Global Oil

Este directorio contiene la documentacion de la etapa de migracion historica cotizada a DATAIA ENGINEERING S.A.S.

## Estado actual

**Fase:** planeacion y diagnostico inicial.

**No se ha ejecutado ninguna carga ni se han creado scripts de migracion en esta fase.**

Los archivos recibidos son evidencia de origen. No se modifican ni se usan como base de sobrescritura de informacion en la plataforma.

## Orden de lectura

1. [00_ALCANCE_Y_GOBIERNO.md](00_ALCANCE_Y_GOBIERNO.md): contrato, limites, responsables y control de cambios.
2. [01_DIAGNOSTICO_INICIAL.md](01_DIAGNOSTICO_INICIAL.md): fuentes recibidas, hallazgos y decisiones que requieren aprobacion.
3. [02_MATRIZ_HOMOLOGACION.md](02_MATRIZ_HOMOLOGACION.md): correspondencia propuesta entre origen y modelo destino.
4. [03_PLAN_PRUEBAS_LOCALES.md](03_PLAN_PRUEBAS_LOCALES.md): como probar cada hito localmente antes de autorizar la carga completa.
5. [04_ACEPTACION_Y_ENTREGA.md](04_ACEPTACION_Y_ENTREGA.md): evidencias de cierre, entrega y aceptacion.
6. [05_MAPA_TABLAS_Y_RELACIONES.md](05_MAPA_TABLAS_Y_RELACIONES.md): tablas disponibles, relaciones y restricciones del modelo actual.
7. [06_ANALISIS_FUENTES_Y_APROVECHAMIENTO.md](06_ANALISIS_FUENTES_Y_APROVECHAMIENTO.md): aprovechamiento de los dos Excel y decisiones pendientes.
8. [07_ETL_Y_HOMOLOGACION_ASISTIDA.md](07_ETL_Y_HOMOLOGACION_ASISTIDA.md): scripts, propuestas locales y condición de entrada al piloto.

## Regla de aprobacion

Ninguna regla que cambie el significado de un dato historico se implementa ni se aplica sin una aprobacion escrita de DATAIA. La aprobacion debe identificar regla, responsable, fecha y alcance.

## Fuentes bajo control

| Identificador | Archivo | Uso autorizado |
| --- | --- | --- |
| F-01 | `REPORTES 2026 CORTO 20 SEPTIMBRE.xlsx` | Fuente de reportes y resultados historicos. |
| F-02 | `Base_Conocimiento_Aceites_v9.xlsx` | Fuente de criterios tecnicos y repertorio. |
| C-01 | `Propuesta_Migracion_Global_Oil_Pago_Contra_Entrega.pdf` | Referencia contractual de alcance y entregables. |

Las copias de trabajo se conservaran fuera de los repositorios de codigo y no se incluiran en Git.

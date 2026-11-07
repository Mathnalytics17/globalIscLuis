# Alcance y gobierno

## Objetivo contratado

Migrar de forma estructurada, verificable y trazable la informacion historica recibida de Global Oil a la plataforma local de gestion de muestras y analisis de lubricantes.

## Entregables contractuales y evidencia esperada

| N. | Entregable | Evidencia de esta carpeta |
| --- | --- | --- |
| 1 | Diagnostico | `01_DIAGNOSTICO_INICIAL.md`, inventario y decisiones aprobadas. |
| 2 | Codigo fuente | Procesos versionados y pruebas automatizadas. Pendiente de implementacion. |
| 3 | Reglas de homologacion | `02_MATRIZ_HOMOLOGACION.md` aprobada. |
| 4 | Informacion migrada | Resumen de ejecucion, registros cargados y excepciones. Pendiente de ejecucion. |
| 5 | Informe de validacion | Conciliacion, muestra revisada e incidencias. Pendiente de ejecucion. |
| 6 | Documentacion tecnica | Esta carpeta, instrucciones de configuracion y operacion. |
| 7 | Entrega final | Paquete y acta descritos en `04_ACEPTACION_Y_ENTREGA.md`. |

## Incluido

- Diagnostico de las fuentes entregadas.
- Definicion aprobada de homologacion, transformacion y criterios de aceptacion.
- Desarrollo posterior de procesos de extraccion, normalizacion, validacion y carga.
- Prueba local, conciliacion, trazas de ejecucion y reporte de excepciones.
- Transferencia de los procesos y documentacion tecnica.

## Excluido

- Modulos nuevos o redisenos sustanciales de plataforma.
- Digitalizacion manual masiva o reconstruccion de datos no recibidos.
- Correccion de errores historicos sin una regla aprobada y evidencia de origen.
- Nuevas fuentes, periodos, estructuras o integraciones que aumenten materialmente el esfuerzo.
- Infraestructura, licencias y soporte operativo de 2027.

## Responsabilidades

| Parte | Responsabilidad |
| --- | --- |
| Contratista | Mantener reserva, documentar, implementar procesos acordados, producir evidencias y corregir defectos reproducibles atribuibles a esos procesos. |
| DATAIA | Proveer archivos, accesos y ambiente local; designar interlocutor; decidir ambiguedades; aprobar reglas y aceptar hitos. |
| Global Oil | Aclarar datos historicos cuando DATAIA lo solicite a traves de su interlocutor. |

## Hitos de decision

| Hito | Quien aprueba | Sin aprobacion no se puede |
| --- | --- | --- |
| Inventario de fuentes | DATAIA | Definir que entra en la migracion. |
| Reglas de homologacion | DATAIA y criterio tecnico de Global Oil cuando aplique | Transformar o cargar datos ambiguos. |
| Resultado del piloto | DATAIA | Ejecutar carga completa. |
| Plan de respaldo y recuperacion | DATAIA | Ejecutar carga definitiva. |
| Informe de validacion | DATAIA | Cerrar la entrega. |

## Control de cambios

Todo cambio de alcance se registra con identificador, fecha, solicitante, descripcion, impacto en fuentes o tiempo, decision y aprobador. Las nuevas fuentes o cambios de estructura no se incorporan por defecto.

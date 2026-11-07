# 06. Análisis de fuentes y aprovechamiento

**Estado:** borrador para homologación.  
**Regla de esta fase:** se inspeccionan los archivos; no se carga, transforma ni elimina información.

## 1. Fuentes recibidas

| ID | Archivo | Aporte | Integridad (SHA-256) |
|---|---|---|---|
| F-01 | `REPORTES 2026 CORTO 20 SEPTIMBRE.xlsx` | Historial operativo y de análisis | `4bf34fd7925df6cb19416ee8a2055f9f83389cfcbcf3c79c81cdb0c59908cab0` |
| F-02 | `Base_Conocimiento_Aceites_v9.xlsx` | Reglas y catálogos técnicos de referencia | `e3d0e7820c5ba5bdc4400cb20e7ba840109cfdee24c0d64e3db522d141aa3618` |

Las copias identificadas con `(1)` tienen el mismo contenido y huella. Los archivos fuente se conservan fuera del repositorio; no se versionan ni se modifican en esta etapa.

## 2. F-01: historial de reportes

La hoja `Reporte OA` tiene 708 registros con OA única y 114 columnas. La hoja `Hoja2` contiene una clasificación auxiliar de clientes. Esto es suficiente para reconstruir un historial, pero no para cargarlo de forma automática sin cerrar las homologaciones.

### 2.1 Información aprovechable

| Bloque de origen | Volumen observado | Destino candidato | Tratamiento propuesto |
|---|---:|---|---|
| `OA` | 708 valores únicos | Referencia histórica de la muestra o reporte | Conservar íntegro; no sustituirlo por el consecutivo interno. Falta decidir su campo definitivo. |
| `FECHA`, `FECHA TOMA DE MUESTRA` | 708 registros | `Muestra` y, si aplica, `Reporte` | Mantener ambas fechas con su significado original; se validan fechas futuras y vacías antes de insertar. |
| `CLIENTE`, `EQUIPO`, `PLACA`, `LUBRICANTE` | 27, 177, 436 y 118 valores distintos | `Empresa`, `Maquina`, `PuntoMuestreo`, `Lubricante` | Crear o vincular solo tras homologación; las coincidencias por texto no se aprobarán automáticamente. |
| Períodos y unidades de servicio/equipo | 434 y 432 períodos distintos | Atributos técnicos de `Muestra` | Cargar únicamente números y unidades válidas; `NR`, `#VALUE!`, vacíos y ambiguos quedan como dato original o en cuarentena, nunca como cero. |
| 18 propiedades físico-químicas y 24 metales | Mediciones históricas | `Prueba` + `PruebaMuestra` | Conservar valor, unidad y calificador. Valores como `<1` no se reducen a un número sin la regla aprobada. |
| `CONCLUSIÓN`, `COM_1` a `COM_10` | Conclusión en 705 registros; comentarios de densidad decreciente | `VersionInterpretacion` y, si corresponde, `Reporte` | Importar como interpretación histórica congelada; no recalcular textos con reglas nuevas. |
| `Tipo`, `Viscosidad`, `Esp_Cal`, `Responsable` | 10, 27, 24 y 3 valores distintos | Atributos/catálogos y trazabilidad | Homologar primero normalización, unidades, sinónimos y responsabilidad. |

### 2.2 Información que no se inferirá

Los campos `INPUT`, `Limit` y `Observacion` no tienen semántica suficientemente demostrada por el archivo. Se preservarán en el registro de origen y no alimentarán límites, reglas ni cálculos hasta que Global Oil valide su significado y procedencia.

La columna `FECHA` tampoco se asumirá como fecha de emisión de reporte hasta acordar la regla. La fecha de toma de muestra se conserva separada de ella.

## 3. F-02: base de conocimiento

F-02 no es un historial de muestras. Es una base técnica que debe entrar como configuración **versionada**, separada de los resultados heredados.

| Hoja | Contenido | Destino candidato | Restricción inicial |
|---|---|---|---|
| `01_Limites_Metales` | Límites por tipo de sistema y metal | Catálogo técnico, campos, fuentes y criterios de límite | No reinterpretar resultados anteriores con estos límites sin aprobación. |
| `02_Viscosidad` | Rangos por grado, mínimo, máximo e índice | Catálogo de viscosidad y valores versionados | Resolver antes equivalencias entre grados/estándares. |
| `03_Degradacion` | Parámetros, método, aplicación, límite e interpretación | Pruebas, fuentes de límite y notas técnicas | No convertir texto condicional en automatización durante esta fase. |
| `05_ISO4406` | Códigos ISO, sensibilidad y componentes | Escalas y catálogo de contaminación | Revisar compatibilidad con la prueba y unidad existentes. |
| `06_Origenes_Metales` | Orígenes y sistemas asociados a metales | Descripciones técnicas de catálogo | Referencia documental; no diagnóstico automático. |
| `07_Repertorio` | Frases y tono para informes | Repertorio técnico/documental | No regenerar las conclusiones históricas. |
| `10_Notas_Tecnicas` | Notas de contexto | Metadatos de la versión del catálogo | Deben quedar ligados a la versión publicada. |

## 4. Decisiones que desbloquean una carga de prueba

1. **D-01 — OA:** confirmar dónde se almacenará y cómo se garantizará su unicidad y búsqueda.
2. **D-02 — Maestros:** aprobar reglas explícitas para cliente, equipo, placa, lubricante y punto de muestreo; las dudas van a una cola de homologación.
3. **D-03 — Períodos:** definir unidades permitidas y cómo conservar valores no numéricos.
4. **D-04 — Mediciones calificadas:** definir el modelo de valores `<x`, `>x`, `ND` y similares, sin perder el texto original.
5. **D-05 — Fechas:** definir el significado de `FECHA` y el manejo de fechas incoherentes o futuras.
6. **D-06 — Interpretaciones:** confirmar que conclusión y comentarios se importan como evidencia histórica, sin recalcularse.
7. **D-07 — Campos opacos:** definir `INPUT`, `Limit` y `Observacion`, o autorizar que permanezcan solo como trazabilidad de origen.

## 5. Orden seguro para la prueba local

1. Registrar F-01 y F-02 en una `CorridaImportacion`, con huella, versión de reglas y responsable.
2. Publicar una versión de los catálogos técnicos derivados de F-02, sin aplicarla retrospectivamente.
3. Ejecutar la homologación revisable de los maestros de F-01; no crear duplicados donde haya incertidumbre.
4. Cargar un lote piloto acotado de muestras y atributos históricos.
5. Cargar pruebas/mediciones y luego las interpretaciones históricas congeladas.
6. Conciliar totales, OA, fechas, valores calificados, comentarios y registros en cuarentena antes de ampliar el lote.

## 6. Resultado de esta revisión

Los dos archivos sí aportan lo necesario para una migración histórica controlada: F-01 aporta los eventos y resultados, y F-02 aporta el marco técnico. El entorno local actual no trae el catálogo completo de pruebas ni los maestros necesarios, por lo que la siguiente actividad no es cargar: es aprobar la matriz de homologación y preparar un lote piloto totalmente reversible.

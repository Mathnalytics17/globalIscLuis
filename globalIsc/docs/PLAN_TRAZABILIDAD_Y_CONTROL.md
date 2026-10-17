# Plan de trazabilidad y control operativo

## Propósito

Convertir la trazabilidad existente —hoy distribuida entre muestras,
resultados, límites, reportes y seguridad— en una capacidad de gestión. El
resultado final será un módulo donde un administrador pueda investigar qué
cambió, quién lo hizo, por qué, qué datos estaban vigentes y qué decisiones
pueden verse afectadas.

Este plan conserva los historiales especializados actuales. No propone una
bitácora genérica que sustituya el historial de un resultado, el *snapshot* de
un reporte o una versión de límites: los conecta y hace consultables desde un
único lugar.

## Fase 1 completada en la rama `trazabilidad`

La Fase 1 incorpora la infraestructura transversal
`EventoAuditoriaOperativa`, la línea de tiempo en el detalle de un lote y la
captura de eventos de lote, muestra, laboratorio, asignación de pruebas,
resultados, revisión, interpretación y reportes. Los eventos nuevos conservan
empresa, máquina y punto de medición cuando la muestra los tiene asociados.

También se añadió `VersionInterpretacion`: cada guardado crea una versión
inmutable y los reportes nuevos quedan ligados a la versión exacta utilizada.
Cuando un reporte se genera desde una interpretación anterior a esta mejora,
se crea una versión explícitamente marcada como `legado`.

La línea de tiempo comienza a poblarse desde el despliegue de esta entrega. Los
historiales especializados ya existentes se conservan intactos; su migración o
consulta unificada como eventos históricos se evaluará antes de activar el
módulo central de la Fase 3.

### Cobertura entregada

- Lote y muestra: creación, edición, cancelación/reapertura, recepción de
  laboratorio, invalidación/reactivación y asignación o reasignación de punto.
- Pruebas: asignación individual o masiva, modificación de configuración y
  retiro permitido antes de registrar mediciones.
- Resultados: registro, borrador/confirmación, edición directa, corrección,
  invalidación, revisión individual y revisión completa del lote. El historial
  de correcciones ahora reconstruye correctamente cada transición.
- Interpretación y reportes: versiones inmutables de interpretación, vínculo
  de la versión exacta al reporte, generación, aprobación, publicación,
  ocultamiento, envío, anulación y sus fallos de envío.
- Consulta: la línea de tiempo del lote está paginada, aislada por empresa y
  conserva actor, motivo, contexto técnico y valores antes/después.

No se reescribieron los historiales preexistentes. Los nuevos eventos se
registran desde esta versión; el *backfill* de evidencia anterior y el panel
administrativo transversal pertenecen a la Fase 3.

## Principios de diseño

1. **No reescribir evidencia.** Una corrección, anulación o cambio de regla
   crea un nuevo evento o versión; no altera la evidencia anterior.
2. **Antes, después y motivo.** Todo cambio operativo relevante registra
   actor, fecha, valores anterior/nuevo, motivo y origen.
3. **Contexto técnico.** Los eventos deben poder relacionarse con empresa,
   lote, muestra, máquina, punto de medición, prueba y reporte.
4. **Aislamiento por empresa.** Un usuario solo ve eventos de las empresas a
   las que tiene acceso; los administradores globales ven el alcance total.
5. **La trazabilidad debe servir para decidir.** Además de una línea de
   tiempo, se deben destacar correcciones posteriores a revisión o reporte,
   cambios de límites y eventos de importación.
6. **Escalable para migración.** Las consultas de histórico y tendencias se
   filtran en el servidor; no se cargan todas las muestras al navegador.

## Estado de partida

| Dominio | Evidencia disponible | Brecha principal |
|---|---|---|
| Muestras | `HistorialMuestra`: cambios antes/después, actor, invalidación y reactivación | Falta integrarlo al lote y exigir motivo según etapa |
| Resultados | `HistoricoResultado` y `RevisionResultado`; corrección con justificación | Múltiples correcciones no expresan la versión posterior de cada evento |
| Límites | `PruebaFuenteLimite` versionada; la asignación fija la fuente usada | Falta comparación rica, actor y motivo de publicación |
| Catálogos | `CatalogoTecnicoVersion`, vigencia y notas | Falta diferencia entre versiones y autor del cambio |
| Reportes | Versiones, *snapshot*, aprobación, anulación y envíos | Falta comparador entre versiones y línea de publicación/envío visible |
| Activos | Historial de asignación muestra–punto (`AsignacionPuntoMuestreo`) | Máquina y punto no registran su ficha antes/después |
| Lotes | Cancelación, reapertura e ingreso de laboratorio auditados puntualmente | No hay línea de tiempo completa del flujo |
| Seguridad | `UserAuditLog` para usuarios, roles, empresas y accesos | No es una auditoría operacional transversal |
| Importaciones | El resultado puede registrar origen de carga | Falta una entidad de corrida, archivo fuente, filas y reversión |

---

## Fase 1 — Evidencia operacional confiable

### Objetivo

Completar la trazabilidad del flujo crítico de muestras antes de exponer un
panel central. Esta fase cubre lote, muestra, pruebas, resultados, revisión,
interpretación y reporte.

### Alcance funcional

1. **Línea de tiempo del lote**
   - Crear, editar, recibir, ingresar a laboratorio, asignar pruebas,
     ingresar resultados, completar revisión, generar reporte, cancelar y
     reabrir.
   - Mostrar responsable, fecha, motivo, entidad relacionada y enlace directo.
   - Incluir eventos de cada muestra como eventos anidados o filtrables.

2. **Pruebas y resultados**
   - Registrar alta, confirmación, cambio de configuración, retiro permitido y
     selección de fuente de límite.
   - Convertir la corrección de resultados en versiones reales: cada versión
     debe conservar el valor completo resultante, no solo el valor previo.
   - Ordenar el historial de resultados cronológicamente y mostrar la
     diferencia por campo.
   - Exigir justificación para correcciones, invalidaciones y acciones que
     ocurran después de la recepción en laboratorio.

3. **Interpretación y reportes**
   - Crear `VersionInterpretacion` con borrador, revisión y aprobación.
   - Registrar contenido, autor, fecha, motivo de reemplazo y origen
     (`manual`, `importación`, `IA`).
   - Relacionar una versión de interpretación con cada reporte generado.
   - Mostrar la cronología de generación, aprobación, publicación, envío,
     anulación y sustitución del reporte.

4. **Contrato técnico usado**
   - Conservar en cada prueba asignada la fuente y versión de límites, criterio
     seleccionado y resultado de evaluación.
   - Nunca reevaluar silenciosamente un resultado histórico con límites
     posteriores.

### Cambios técnicos

- Introducir una entidad append-only `EventoAuditoriaOperativa` para enlazar
  eventos de dominio, sin reemplazar `HistorialMuestra`,
  `HistoricoResultado`, `RevisionResultado` ni `Reporte.snapshot`.
- Campos mínimos: `fecha`, `actor`, `empresa`, `tipo_entidad`,
  `entidad_id`, `accion`, `motivo`, `estado_anterior`, `estado_nuevo`,
  `origen`, `lote`, `muestra`, `maquina`, `punto_muestreo`, `prueba`,
  `reporte` y `correlation_id`.
- Crear una función de servicio única para registrar eventos dentro de la misma
  transacción de negocio.
- Agregar índices por empresa/fecha, entidad/identificador, lote, muestra,
  máquina, punto, acción y actor.
- Mantener la autorización en el servidor y reutilizar el aislamiento por
  empresa ya aplicado a lotes y resultados.

### Criterios de aceptación

- Desde el detalle de un lote se puede reconstruir el flujo completo sin abrir
  varias pantallas.
- Un resultado corregido dos o más veces muestra cada valor anterior y
  posterior correcto, usuario, fecha y justificación.
- Un reporte permite identificar qué versión de interpretación, resultados y
  límites le dio origen.
- Los cambios posteriores a laboratorio no se guardan sin motivo cuando la
  política de la acción lo exige.
- Un usuario de empresa no puede consultar eventos de otra empresa, ni por URL
  ni por parámetros de filtro.

### Entregables

- Migraciones, modelos, servicios y pruebas de autorización/regresión.
- Historial de lote y mejoras al historial de resultado.
- Versionado de interpretación y trazabilidad de reporte.
- Documento de contrato de eventos y política de retención.

---

## Fase 2 completada en la rama `trazabilidad`

Esta rama ya registra cambios de máquina y punto de medición (alta, edición,
desactivación, reactivación y reasignación de muestras) y expone su actividad
paginarla por API. La ficha de la máquina muestra los eventos recientes.

También se instrumentaron pruebas, catálogos, escalas, métodos, equipos de
prueba, unidades y configuración de límites; las operaciones de publicar una
versión, regenerar campos e importar una matriz conservan antes/después y el
origen de importación. Los comparadores de límites y catálogos ya muestran la
diferencia entre una versión histórica y la vigente sin exponer JSON técnico.
Finalmente, el histórico de máquina dejó de descargar las muestras de todos los
equipos: consulta resultados paginados en el servidor para la máquina
seleccionada, aplicando filtros de punto, prueba e inclusión explícita de
muestras invalidadas.

Desde el árbol de activos, cada punto de medición ya permite abrir su actividad
reciente. La ficha de máquina muestra los eventos de la máquina y de los puntos
asociados. Ambas consultas respetan el alcance de empresa y se sirven de forma
paginada.

### Límites actuales de alcance

- El comparador de catálogos trae como máximo 1.000 ítems por versión y advierte
  visualmente cuando el catálogo es mayor. La comparación paginada íntegramente
  en servidor queda como optimización de volumen para una fase posterior.
- La navegación detallada desde una tendencia permanece en el registro histórico
  de la misma pantalla; el módulo transversal de investigación y los enlaces
  completos a lote, reporte y contrato de límites pertenecen a la Fase 3.

### Objetivo

Proteger el contexto que hace útil una tendencia: máquina, punto de medición,
lubricante, prueba, escala, catálogo y límites.

### Alcance funcional

1. **Máquinas y puntos de medición**
   - Historial de creación, edición, activación/desactivación, lubricante,
     frecuencia de cambio/análisis y datos técnicos.
   - Historial visible de reasignaciones de muestra entre puntos, con punto
     anterior, nuevo punto y motivo.
   - Pestaña `Actividad e historial` en máquina y punto.

2. **Configuración técnica**
   - Auditar cambios de pruebas, campos, componentes, métodos, unidades,
     condiciones, escalas, catálogos y plantillas de pruebas.
   - Para límites y catálogos, agregar comparación visual entre dos versiones:
     campos añadidos, eliminados o modificados.
   - Guardar autor, motivo, fecha de vigencia y estado de publicación de cada
     versión técnica.

3. **Histórico y tendencias escalables**
   - Reemplazar la carga global `include_muestras=1` por un endpoint de
     tendencias filtrado por empresa, máquina, punto, prueba y rango de fechas.
   - Paginar la tabla de registros en el servidor.
   - Excluir muestras invalidadas por defecto, permitiendo incluirlas con una
     marca visual explícita.
   - Agregar navegación desde un punto de gráfica a muestra, lote, reporte y
     contrato de límites utilizado.

### Criterios de aceptación

- Un administrador puede saber quién cambió el lubricante de un punto y desde
  cuándo.
- Una muestra reasignada conserva su relación anterior y esta se ve desde el
  punto, la muestra y el evento central.
- Dos versiones de límites o catálogo se pueden comparar sin inspeccionar
  JSON ni exportar datos.
- Consultar una máquina con miles de muestras no requiere descargar toda la
  historia al navegador.

### Entregables

- Auditoría de activos y configuración.
- Comparadores de versiones de límites y catálogos.
- API de tendencias paginada y filtros avanzados.
- Pruebas de rendimiento básico, aislamiento de empresa y regresión de
  tendencias.

---

## Fase 3 — Módulo “Trazabilidad y control” e importaciones

### Objetivo

Entregar la vista administrativa transversal para investigar cambios y tomar
decisiones, y dejar preparada la operación para cargas históricas masivas.
La IA asistiva queda explícitamente fuera de este alcance hasta que exista una
aprobación comercial independiente.

### Módulo principal

Ruta propuesta: `/trazabilidad`

Subsecciones:

1. **Actividad**
   - Tabla cronológica unificada.
   - Filtros: período, empresa, entidad, acción, usuario, lote, muestra,
     máquina, punto, prueba, reporte, origen y criticidad.
   - Panel de detalle con antes/después, motivo, contexto y enlaces.

2. **Cambios críticos**
   - Resultados corregidos después de revisión o reporte.
   - Muestras invalidadas.
   - Lotes cancelados/reabiertos.
   - Límites o catálogos publicados recientemente.
   - Reasignaciones que afectan tendencias.
   - Eventos de importación fallidos o parcialmente aplicados.

3. **Versiones técnicas**
   - Búsqueda y comparador de límites, catálogos, escalas, pruebas e
     interpretación.

4. **Importaciones**
   - Corrida de importación, archivo fuente, usuario, fecha, conteos,
     advertencias, errores y entidades creadas/actualizadas.
   - Previsualización, validación, confirmación y reversión controlada por
     corrida cuando sea técnicamente segura.

### Criterios de aceptación

- Un administrador puede responder desde una sola pantalla qué cambió en una
  empresa, máquina, punto, prueba o período.
- Cada fila enlaza a la entidad original y muestra evidencia suficiente para
  tomar una decisión.
- Los cambios críticos se identifican sin que el usuario tenga que conocer el
  identificador de una muestra o lote.
- Una importación masiva deja evidencia de su fuente, transformación, errores
  y resultado.

### Entregables

- Módulo frontend y API de trazabilidad paginada.
- Vistas de control, comparadores y exportación filtrada.
- Bitácora de importaciones y documentación ETL.
- Política de auditoría, retención, respaldo y acceso por rol.

---

## Política de conservación y seguridad

- Los datos operativos cerrados no se eliminan físicamente; se invalidan,
  anulan o desactivan con motivo.
- Las entidades de evidencia no se editan después de creadas. Las correcciones
  crean versiones posteriores.
- Los eventos de auditoría no se exponen a usuarios fuera de su alcance de
  empresa o permiso.
- Las capturas de reportes emitidos permanecen inmutables.
- Las ejecuciones ETL conservan sus archivos o una referencia verificable al
  archivo fuente, según la política de retención acordada con el cliente.
- Las copias de seguridad y exportaciones deben tener acceso restringido y
  registrar quién las solicita.

## Dependencias entre fases

```text
Fase 1: evidencia confiable del flujo de muestras
    ↓
Fase 2: contexto técnico y tendencias auditables
    ↓
Fase 3: consulta central, importación masiva e IA asistiva
```

La Fase 3 no debe adelantarse: el módulo central solo será útil si los eventos
de las dos primeras fases son completos, autorizados y técnicamente
consistentes.

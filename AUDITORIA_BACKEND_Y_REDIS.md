# Auditoría de backend y uso de Redis

Fecha: 2026-11-06  
Alcance: todos los módulos incluidos en `INSTALLED_APPS`, sus rutas API y
servicios de lectura. La auditoría no trata directorios auxiliares que no son
aplicaciones Django instaladas (`administrationPanel`, `documents` y `media`),
porque no exponen código de ejecución en el backend actual.

## Principios aplicados

1. Primero se corrige la consulta; Redis no compensa un patrón N+1 ni una
   respuesta innecesariamente grande.
2. Ninguna entrada de caché se comparte entre usuarios. Esto conserva el
   alcance por empresa y las reglas RBAC.
3. Una escritura confirmada invalida la versión correspondiente. Si la
   transacción falla, no se invalida ni se publica información intermedia.
4. Las rutas que cambian información, manejan sesión, seguridad, archivos,
   cálculos de resultados o PDF no se cachean.
5. Si Redis deja de responder, las listas de máquinas siguen desde PostgreSQL.
   La caché no puede volver indisponible la operación.

## Correcciones implementadas

| Módulo | Corrección aplicada | Efecto |
| --- | --- | --- |
| `activesTree` | La lista de máquinas ahora anota el número de puntos activos y calcula ubicaciones del árbol en bloque. | Elimina consultas por máquina al contar puntos y reconstruir la ruta. |
| `activesTree` | Caché de la lista normal de máquinas, aislada por usuario y parámetros. | Acelera cargas repetidas sin exponer datos entre empresas. |
| `activesTree` | Invalidación tras confirmar cambios de empresa, máquina, punto o carpeta. | No conserva listas de activos después de editar el árbol. |
| `dashboard` | Las alertas de pruebas precargan lote, cliente, gestión y muestras; los filtros de cliente/gestión se obtienen con `values_list().distinct()`. | Evita cargas repetidas de muestras y materializar lotes completos solo para llenar selectores. |
| `reporte` | Los envíos de un reporte precargan quien envió y el destinatario. | Evita una consulta adicional por usuario al serializar envíos. |

## Revisión por módulo

### `activesTree`

Estado: corregido y cacheado en la vista de mayor uso (`GET /api/machines/`).
Las relaciones de carpeta, empresa y puntos se evalúan en bloque. Las rutas de
histórico y `include_muestras` quedan fuera de caché por su volumen y porque
requieren datos actuales para las tendencias.

### `muestras`

Estado: revisado. Las listas principales de lotes ya usan anotaciones para
totales/progreso, `select_related`, `Prefetch` y paginación. Las operaciones de
registro, ingreso de laboratorio, asignación, importación y trazabilidad se
mantienen sin caché: son flujos transaccionales o auditablemente sensibles.

No se añadió una caché genérica porque una respuesta puede depender de estado
de lote, asignaciones, permisos, atributos técnicos y resultados. Antes de
cachear una lista concreta se debe medir su endpoint y definir su versión de
invalidación, igual que en Máquinas.

### `resultado`

Estado: revisado. Es el módulo de cálculo, revisión e interpretación. Sus
consultas críticas ya declaran relaciones para pruebas, resultados, divisiones
y componentes. No se cachea: los valores pueden cambiar durante la captura,
revisión o recálculo y servir un resultado anterior sería incorrecto.

Recomendación de operación: medir con `EXPLAIN (ANALYZE, BUFFERS)` las rutas de
tablero de resultados con datos de producción antes de agregar índices nuevos.

### `reporte`

Estado: corregido y cacheado el listado de biblioteca por usuario y filtros,
con TTL de 30 segundos. Cambios confirmados de reporte, envío, muestra, lote,
empresa, máquina o punto de muestreo invalidan la versión. PDF, versiones,
detalle, aprobación, envío y publicación no se cachean: requieren trazabilidad
y estado inmediato.

### `dashboard`

Estado: corregido y cacheado. El centro operativo consolida lotes, pruebas y
reportes; su respuesta se guarda solo 20 segundos, aislada por usuario y
filtros. Cambios confirmados en empresa, gestión, lote, muestra, prueba,
resultado o reporte invalidan la versión inmediatamente. Durante una
transacción abierta el dashboard siempre consulta PostgreSQL.

### `misc`

Estado: cacheado para las lecturas repetitivas de equipos, métodos, unidades,
condiciones, pruebas, configuración técnica, tipos de gestión y lotes de
pruebas predefinidos. La respuesta está aislada por usuario y parámetros y su
TTL es de cinco minutos.

Las señales de todos los modelos que forman esos catálogos elevan una versión
global con `transaction.on_commit`; las relaciones muchos-a-muchos de tipos de
gestión también invalidan la caché. Durante una transacción abierta la caché
se omite por completo: una lectura de la misma operación va a PostgreSQL y
ningún dato sin confirmar puede publicarse en Redis. Compañías, permisos y
datos operativos continúan fuera de esta caché.

### `users`

Estado: revisado. Redis ya respalda sesiones y límites de login/restablecimiento.
No se cachean perfiles, roles, permisos ni alcance de datos: hacerlo podría
permitir que una revocación tarde en aplicarse. La separación `default` /
`sessions` de la configuración se conserva.

### `utils`

Estado: revisado. Solo concentra la paginación estándar, sin consultas propias
ni datos candidatos a Redis.

### Directorios no instalados

`administrationPanel`, `documents` y `media` no aparecen en `INSTALLED_APPS` y
no contienen una API activa de negocio. No se les agregó caché ni cambios.

## Diseño de Redis implementado

Archivo: `globalIsc/apps/activesTree/machine_list_cache.py`.

- Clave: versión de activos + identificador del usuario + hash ordenado de los
  parámetros de consulta.
- TTL: 120 segundos para `GET /api/machines/` normal.
- Aislamiento: la respuesta de un usuario nunca sirve a otro usuario, incluso
  si ambos consultan los mismos parámetros.
- Invalidación: señales `post_save` y `post_delete` de `Empresa`, `Maquina`,
  `PuntoMuestreo` y `Carpeta`; se agenda con `transaction.on_commit`.
- Concurrencia: se verifica que la versión siga igual antes de guardar una
  respuesta. Si ocurrió una modificación mientras se serializaba, esa
  respuesta no entra a la nueva versión de caché.
- Degradación segura: los errores de caché se capturan y registran; PostgreSQL
  sigue siendo la fuente de verdad para este endpoint.

## Validación

Se ejecutó compilación de los archivos modificados, importación de Django con
`backend.settings_test`, validación de espacios del diff y la batería integrada
contra la base de pruebas aislada de PostgreSQL. Resultado: **34 pruebas
ejecutadas, 34 aprobadas** (`activesTree`, `dashboard` y `reporte`).

También se validó el consumidor: el frontend completó `typecheck`, `lint` y
`next build` correctamente. La implementación de Redis no cambia la forma de
las respuestas API: `GET /api/machines/` conserva paginación y todos los
campos que usa la vista (`empresa_info`, `ubicacion_activo` y
`puntos_muestreo_activos`). Dashboard y reportes conservan sus contratos; sus
cambios son exclusivamente de precarga de relaciones.

El lint del frontend mantiene advertencias preexistentes (111), pero no tiene
errores y la compilación de producción fue satisfactoria.

Para repetir la validación dentro de Docker o CI:

```powershell
python manage.py check
python manage.py test apps.activesTree apps.dashboard apps.reporte --settings=backend.settings_test
```

La fase siguiente debe basarse en métricas reales (latencia p95, consultas por
endpoint, tamaño de respuesta y `EXPLAIN ANALYZE`), no en añadir caché de forma
indiscriminada.

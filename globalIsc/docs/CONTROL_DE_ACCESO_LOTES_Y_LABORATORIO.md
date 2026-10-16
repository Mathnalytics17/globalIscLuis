# Control de acceso: lotes, laboratorio y parámetros de URL

## Regla de seguridad

Un valor como `?lote=L20260003`, `/muestras/lotes/L20260003` o
`?muestra=...` identifica el recurso que se quiere consultar. No concede
acceso. La autorización se resuelve exclusivamente en el servidor con el
usuario autenticado y la empresa a la que pertenece.

Esto evita *Broken Access Control* / BOLA (también conocido como IDOR): un
usuario no puede cambiar un identificador en la URL o en el cuerpo de una
petición para consultar, modificar o procesar recursos de otra empresa.

## Capas aplicadas

1. **Navegación y acciones del cliente.** La vista de lotes solo muestra
   acciones de laboratorio, resultados, revisión e interpretación cuando la
   matriz de permisos del usuario las permite. Laboratorio, asignación de
   pruebas, resultados, revisión e interpretación no se montan y redirigen a
   lotes antes de iniciar peticiones si faltan sus permisos.
2. **Autorización de endpoint.** `HasSecurityPermission` exige el permiso
   asociado a cada acción de cada ViewSet.
3. **Aislamiento por empresa.** Los querysets de lotes, ingresos de
   laboratorio, pruebas y resultados se restringen a
   `cliente_empresa=request.user.empresa` para usuarios que no sean Global
   Oil ni superusuarios. Un recurso ajeno responde como inexistente (404)
   cuando corresponde.
4. **Validación al escribir.** La creación de un ingreso de laboratorio
   verifica además que el lote enviado pertenece a la empresa del usuario.
   Esto es necesario porque una relación enviada en el cuerpo no pasa por
   `get_queryset()` de forma automática.

## Endpoints revisados

- `lubrication/sample-batches/` y sus acciones de detalle.
- `lubrication/lab-batch-entries/`, incluida la recepción de un lote.
- Operaciones de resultados: ingreso, historial, corrección, revisión e
  interpretación de lotes, muestras y pruebas.
- Asignación de pruebas por lote.

Los parámetros de consulta se conservan porque permiten enlazar y volver a
una pantalla concreta, pero solo seleccionan dentro de los objetos ya
autorizados por el backend.

## Pruebas de regresión

`apps.muestras.tests.BatchObjectAuthorizationTests` comprueba que un usuario
de Empresa A no puede:

- obtener por URL un lote de Empresa B (404);
- crear un ingreso de laboratorio para ese lote aunque envíe su id en el
  cuerpo de la petición (400 sin crear el ingreso).

Ejecutar:

```powershell
docker exec backend python manage.py test apps.muestras.tests.BatchObjectAuthorizationTests --keepdb
```

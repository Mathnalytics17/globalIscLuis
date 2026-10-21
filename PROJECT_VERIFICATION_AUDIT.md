# Auditoría de verificación local

Fecha: 20 de octubre de 2026. Alcance: los dos repositorios locales (`backend` y
`frontend`) y la base de datos local preparada para pruebas. Este documento no
certifica una puesta en producción; deja trazabilidad de lo que fue ejecutado y
de los escenarios que todavía requieren una prueba funcional con personas.

## Correcciones verificadas en esta revisión

| Área | Hallazgo | Corrección y prueba |
| --- | --- | --- |
| Gestión de usuarios | La tabla mostraba `Sin registro` en **Último acceso** aunque Django actualizaba `User.last_login` al autenticar. El serializador no entregaba ese campo. | `UserSerializer` ahora expone `last_login`. La prueba de sesión confirma que el login persiste el valor y que la respuesta lo contiene. |
| Directorio de usuarios | Cualquier usuario autenticado de una empresa podía consumir directamente `/api/users/` y consultar colegas, aun sin permiso de directorio. | La lista y el detalle de otra persona exigen `empresas.ver_usuarios`; la propia ficha sigue disponible. Hay pruebas positivas y negativas para ambos casos. |
| Catálogos técnicos | Al volver desde un catálogo sin versiones, el drawer de versión podía renderizarse un ciclo sin `versionForm` y detener toda la página. | El drawer ahora recibe siempre su estado completo, tiene un valor seguro por defecto y se cierra antes de cambiar de vista. Una tabla vacía muestra su estado vacío sin provocar error. |
| Versiones de catálogo | El botón genérico del detalle decía `Desactivar` y desactivaba el catálogo padre, no la edición que se estaba viendo. Además, crear una edición la volvía vigente sin una decisión explícita. | El botón se llama ahora `Desactivar catálogo`. En la lista de versiones hay acciones separadas para usar una edición como actual, desactivar una histórica o reactivarla. Crear una versión conserva la vigente. El backend impide desactivar o eliminar la versión actual hasta elegir otra activa. |
| Estado del catálogo | Un catálogo dado de baja no tenía una acción visible para volver a activarlo y aún podía filtrarse hacia el ingreso de muestras mediante rutas operativas. | La lista y el detalle muestran de forma explícita `Activar catálogo` o `Desactivar catálogo`, con estado visible. Las versiones e ítems no se pueden modificar mientras el catálogo esté inactivo; la API de formulario de muestras excluye esos catálogos sin borrar su historial. |
| Magnitudes, unidades y condiciones | La categoría de una unidad y la magnitud de una condición eran texto libre e independientes; se podían repetir o combinar una condición de temperatura con una unidad que no correspondía. | La configuración se organiza como **Magnitud → Unidad → Condición**. La magnitud es un catálogo administrable y único sin distinguir mayúsculas o espacios; cada unidad exige una magnitud y cada condición exige la misma magnitud junto con una unidad compatible. La migración conserva los registros existentes, crea o relaciona magnitudes a partir de sus datos históricos y mantiene la etiqueta antigua sincronizada para integraciones previas. |
| Asistente de límites | La navegación directa a Resumen podía omitir la validación de la matriz y la plantilla Excel no guiaba la selección de operación. | Todo salto hacia adelante valida los pasos intermedios y el guardado siempre revalida la matriz completa. La columna `operacion` de la plantilla Excel ahora es un selector con `max`, `min`, `between`, `eq`, `neq`, `in`, `not_in` e `informativo`, además de una guía que explica cada valor. |
| Matriz Excel y reglas especiales | Una importación podía guardar `eq`, listas u otra regla especial, pero el editor regeneraba otro código para campos con símbolos (por ejemplo `4μm`) y mostraba el valor por defecto `max` vacío. Además, una marca de semáforo podía persistir indebidamente para reglas binarias. | La matriz conserva el código de campo ya guardado, une cada criterio por sus selecciones de catálogo y reconstruye sus reglas sin depender de etiquetas o slugs. La importación valida las ocho operaciones de forma uniforme; solo `max`, `min` y `between` conservan semáforo. Una regresión cubre `max`, `min`, `between`, `eq`, `neq`, `in`, `not_in` e `informativo`. |
| Aislamiento de reportes | Un reporte oculto o no aprobado podía quedar expuesto por variantes de consulta. | La política común para audiencia de empresa exige alcance de compañía, `visible_cliente=True`, estado aprobado y datos de aprobación. También se aplica al historial de versiones. |
| Interpretación | La visualización local de tendencias y su inclusión en el PDF eran el mismo control. | Se separaron en `Mostrar tendencias aquí` e `Incluir tendencias en el informe`; solo el segundo se guarda en `graficas_activas`. |
| Sesión vencida en frontend | Un `401` de una pantalla protegida podía propagarse como `AxiosError` y mostrar el overlay técnico de Next.js, aun cuando el sistema ya conocía que debía volver a iniciar sesión. | El cliente marca y deduplica el vencimiento; Auth limpia la sesión y hace una redirección directa al inicio de sesión. El backend añade `X-Session-Expired: 1` cuando invalida una sesión, por lo que incluso un `403` posterior de esa misma petición se distingue de una denegación RBAC real. |
| Resolución de pantallas | Trece páginas existían dos veces con el mismo módulo en `.js` y `.jsx`. Las rutas sin extensión podían resolver una copia distinta a la que se había modificado. | Se mantuvo una sola implementación por pantalla y se verificó que no quedan pares con la misma ruta base. |

La fecha del último acceso se guarda en UTC y el frontend la convierte a la zona
horaria del navegador. Un usuario que nunca inició sesión seguirá mostrando
`Sin registro`, que ahora sí significa exactamente eso.

## Evidencia automática ejecutada

| Comando | Resultado |
| --- | --- |
| `python manage.py check` dentro de `backend` | Correcto: 0 incidencias. |
| `pytest -q` dentro de `backend` | **151 aprobadas** en 56.95 s, incluida la regresión del directorio y tras reiniciar el servicio local. |
| `pytest apps/users/test_session_security.py apps/users/tests.py -q` | **20 aprobadas** tras añadir las regresiones de último acceso/directorio. |
| `npm run typecheck` en `frontend` | Correcto, sin errores de TypeScript. |
| `npm run lint` en `frontend` | Correcto, sin errores ESLint. |
| `npm run build` | Correcto en una salida aislada: **69 rutas** compiladas y prerenderizadas. El primer intento detectó una carrera con el servidor `next dev` abierto sobre `.next`; se añadió una configuración de verificación que permite usar `NEXT_DIST_DIR` sin contaminar el `tsconfig` de desarrollo. |
| `python manage.py test apps.misc.tests.UnitCategoryApiTests` | Correcto: 1 prueba de flujo aprobada para magnitud única, selector de unidad, sincronización al renombrar, condición compatible y rechazo de una unidad cruzada. |
| `python manage.py test apps.misc.tests.DynamicTechnicalConfigApiTests apps.muestras.test_limit_comparisons --verbosity 1` | Correcto: 12 pruebas aprobadas, incluida importación Excel de las ocho operaciones y comparación tipada. |

## Política de datos que debe mantenerse

Los tres controles son independientes y ningún permiso de interfaz los reemplaza:

1. **Acción:** la matriz RBAC determina si alguien puede, por ejemplo, ver,
   generar, aprobar o publicar.
2. **Alcance de datos:** `OWN_COMPANY`, `ASSIGNED_COMPANIES` o `ALL_COMPANIES`
   decide qué empresas pueden entrar al queryset.
3. **Audiencia:** para una cuenta de empresa, un reporte solo es consultable si
   está aprobado y marcado visible. Global Oil puede operar sobre los reportes
   dentro de su alcance, incluso si aún no fueron publicados al cliente.

Este diseño evita que “tener `reportes.ver`” se interprete como “ver todos los
informes de cualquier empresa” o como “ver borradores internos de su empresa”.
El detalle completo está en `DATA_BOUNDARY_AND_CLEANUP_PLAN.md`.

## Base local de prueba actual

La base fue reiniciada a una línea base de seguridad: **Global Oil** existe como
empresa interna protegida y conserva su administrador global. Existen además
tres empresas cliente de demostración (Minera, Taller e Industria), cada una
con administrador, consulta y carga de muestras. Los roles internos, como
Laboratorista y Revisor, se invitan a Global Oil; los roles de empresa se
invitan únicamente a una empresa cliente. Global Oil no aparece en los
selectores operativos de clientes; Seguridad lo solicita explícitamente para
administrar o invitar personal interno. No hay
lotes, muestras, activos, máquinas, puntos, resultados, reportes ni catálogos
operativos. Las credenciales se administran fuera de este documento.

Comandos disponibles para repetir la preparación sin tocar producción:

```powershell
docker exec backend python manage.py reset_to_security_baseline --yes
docker exec -e DEMO_DEFAULT_PASSWORD='<contraseña-segura>' backend python manage.py seed_clean_demo_baseline --yes --reset-passwords
```

El primer comando conserva usuarios/RBAC y elimina datos operativos; el segundo
reconstruye la línea base de usuarios coherente con sus tres empresas. Hacer un
dump antes de ejecutar cualquiera de los dos.

## Casos que aún requieren validación funcional dirigida

Las pruebas automáticas no sustituyen estas comprobaciones de navegador y de
negocio. Deben ejecutarse antes de declarar el sistema listo para producción:

| Prioridad | Escenario | Criterio de aceptación |
| --- | --- | --- |
| Alta | Matriz de roles desde UI | Cambiar un permiso, guardar, recargar y confirmar que menú, ruta y API cambian de forma consistente. |
| Alta | Aislamiento entre empresas | Con dos empresas reales, intentar leer por URL/API un lote, muestra, activo, resultado, reporte y adjunto de la otra; todos deben responder 403/404 según corresponda. |
| Alta | Flujo completo de una muestra | Crear lote, asignar equipo/punto, recepción de laboratorio, resultados, revisión, interpretación, generación, aprobación y publicación de reporte. |
| Alta | Audiencia de reporte | Verificar que el administrador de empresa no ve un reporte generado/oculto/no aprobado, y que aparece solo después de aprobar y publicar. |
| Alta | Importación Excel | Validar archivo correcto, encabezados inválidos, filas con error, duplicados y el comportamiento transaccional sin datos parciales. |
| Media | Sesiones | Login, logout, cambio/restablecimiento de clave y bloqueo deben revocar la sesión en otra pestaña. |
| Media | Fechas SLA | Confirmar que días hábiles parten de `ingreso_laboratorio`, no de creación, con festivos/calendario configurados. |
| Media | Archivos | Verificar permisos sobre PDF, firmas y adjuntos con URL directa, no solo desde botones. |
| Media | Histórico | Crear al menos dos mediciones válidas del mismo punto/prueba y verificar series, unidades, rango y ausencia de cruces entre empresas. |

## Límites conocidos de la revisión

- No se hicieron llamadas destructivas ni despliegues al servidor durante esta
  auditoría.
- No existe aún una suite E2E de navegador que automatice los flujos de Excel,
  PDF, correo y las 69 páginas. Esa es la principal mejora de calidad pendiente:
  incorporar Playwright con datos efímeros y un usuario por rol.
- Los servicios externos (Redis, correo y almacenamiento de archivos) fueron
  cubiertos en sus contratos locales y mocks, no con un proveedor de producción.

## Recomendación para probar en paz

Primero use la base limpia local y ejecute los casos de prioridad alta en el
orden mostrado. Registre cada resultado con usuario, empresa, URL y evidencia.
Cuando esos casos pasen, se puede aplicar la misma línea base en el servidor con
backup previo y repetir allí una pasada reducida de aislamiento, importación y
reporte. No migre semillas antiguas: fueron precisamente las que introdujeron
reportes inconsistentes.

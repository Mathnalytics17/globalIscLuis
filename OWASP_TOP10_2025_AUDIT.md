# Auditoría OWASP Top 10 2025 — GlobalOil

Fecha: 2026-10-14  
Alcance: código backend Django/DRF, frontend Next.js, Docker/Nginx, CI/CD y dependencias instaladas localmente.  
Método: inspección estática de rutas, autorizaciones, entradas, renderizado, configuración y manifiestos; ejecución de `manage.py check --deploy` en el entorno **local** y `npm audit --omit=dev`. No se realizaron ataques contra producción, pruebas de acceso no autorizado ni escaneos externos.

## Cómo leer este informe

- **Confirmado**: el código o la configuración permite el comportamiento descrito.
- **Requiere prueba controlada**: existe una superficie plausible, pero no se ejecutó un payload contra un entorno real.
- **Control presente**: se comprobó una defensa relevante; no equivale a que la categoría esté completamente cerrada.
- **Corregido en esta rama**: se detectó antes y ya tiene cambio y prueba de regresión local.

Los números de línea son enlaces para abrir el punto exacto desde Codex. Si el archivo evoluciona, usa el título de la sección o el símbolo indicado para localizarlo.

## Resumen ejecutivo

| Estado | Cantidad | Qué significa |
|---|---:|---|
| Crítico corregido | 2 | Autoelevación de rol y generación/previsualización de reportes de otra empresa. |
| Alto pendiente | 3 | SSRF en PDF, XSS en vistas de documentos y archivos de media públicos. |
| Medio pendiente | 10 | Configuración, cargas Excel, trazabilidad y cadena de suministro. |
| Controles comprobados | 8 | Sesión Redis, CSRF, rate-limit de login/reset, aislamiento en la mayoría de ViewSets, HSTS/CSP de Nginx, etc. |

No es correcto afirmar que una auditoría de código local encuentre *todas* las vulnerabilidades posibles. Para cerrar la auditoría hacen falta pruebas autenticadas por rol/empresa, revisión del host de producción, análisis SCA de Python, escaneo de imagen y pentest controlado. Este informe deja identificadas todas las superficies encontradas en el alcance indicado.

---

## A01 — Broken Access Control

### A01-01 — Corregido: autoelevación de privilegios por `role` — Crítico

Un usuario podía editarse a sí mismo en `PATCH /api/users/<id>/`; el serializador exponía `role` como campo modificable. `User.Role.GLOBAL` otorga todos los permisos en la matriz.

- Corrección: [`UserDetailSerializer`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/users/api/serializers/index.py:121) marca `role` como solo lectura y rechaza cambios de estado sensibles sobre la propia cuenta.
- Punto de autorización: [`UserDetailView`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/users/api/views/user/index.py:338).
- Privilegio global: [`user_has_permission`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/users/api/services.py:422).
- Prueba: [`test_user_cannot_elevate_own_role_or_access_status`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/users/test_session_security.py:87).

### A01-02 — Corregido: reportes sin filtro de empresa — Crítico

Las acciones de generar, generar por lote y previsualizar buscaban por ID sin exigir que la muestra/lote perteneciera a la empresa del solicitante.

- Corrección de ámbito: [`_tenant_samples_queryset`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/reporte/api/views/index.py:405).
- Aplicación a creación y acciones de generación: [`perform_create`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/reporte/api/views/index.py:431), [`generate_from_interpretation`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/reporte/api/views/index.py:584), [`generate_batch_from_interpretation`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/reporte/api/views/index.py:602) y [`preview_from_interpretation`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/reporte/api/views/index.py:631).
- Prueba de aislamiento: [`test_tenant_sample_scope_excludes_another_company`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/reporte/tests.py:208).

### A01-03 — Media público sin autorización — Alto

Nginx expone todo `/media/` mediante `alias`, sin autenticar ni comprobar empresa. Las firmas se guardan bajo esa raíz. Conocer o adivinar una URL basta para leer el archivo.

- Exposición: [`location /media/`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/nginx/conf.d/aladino.conf:75).
- Firma de usuario: [`ImageField`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/users/api/models/index.py:77).
- Firma cargada por reportes: [`upload_signature`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/reporte/api/views/index.py:1021).

**Remediación propuesta:** servir archivos privados desde una vista autenticada que valide empresa y emita una URL temporal; limitar `/media/` público a logos estáticos no sensibles.

### A01-04 — Centro operacional sin permiso específico — Medio/alto, requiere decisión de negocio

El endpoint completo y el envío del resumen diario exigen solamente autenticación. Además, `ADMIN` y `LABORATORISTA` reciben todos los lotes en el servicio del dashboard.

- Ruta: [`OperationalCenterViewSet`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/dashboard/api/views/index.py:22).
- Alcance de datos: [`scoped_batches_for_user`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/dashboard/api/services/operational_center.py:44).

Si `ADMIN` representa a un administrador de empresa, esto es exposición cruzada de tenants y debe corregirse. Si es exclusivamente personal interno de GlobalOil, documentar esa regla y sustituir el rol heredado por un permiso explícito sigue siendo recomendable.

### A01-05 — Previsualización de límites con muestra por ID — Medio, requiere prueba controlada

`resolve_preview` consulta `Muestra.objects.get(pk=...)` directamente. La ruta requiere `valores_limite.ver`, pero no aplica alcance por empresa.

- Punto: [`resolve_preview`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/misc/api/views/dynamicTechnicalConfig/index.py:721).

Debe definirse si usuarios de configuración pueden consultar datos de cualquier empresa. Si no, reutilizar un queryset por tenant.

### Controles A01 presentes

- Las principales vistas de lotes filtran por `cliente_empresa`: [`LoteMuestrasViewSet.get_queryset`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/muestras/api/views/loteMuestras/index.py:55).
- Resultados filtran por empresa a través del lote: [`ResultadoViewSet.get_queryset`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/resultado/api/views/index.py:1364).
- La matriz de permisos se aplica a la mayoría de ViewSets mediante [`HasSecurityPermission`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/permissions.py:101).

---

## A02 — Security Misconfiguration

### A02-01 — Código fuente montado en el compose de producción — Medio

Los contenedores de aplicación montan `./globalIsc` sobre la imagen construida. Un cambio en el host altera el runtime sin una imagen inmutable, revisión ni firma.

- [`web.volumes`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/docker-compose.prod.yml:25)
- [`daphne.volumes`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/docker-compose.prod.yml:44)

### A02-02 — Valores de desarrollo como fallback — Medio

El secreto Django se exige en producción, lo cual es correcto; no obstante, la contraseña PostgreSQL tiene un valor por defecto de desarrollo. Un despliegue incompleto podría arrancar con una contraseña conocida.

- [`POSTGRES_PASSWORD` fallback](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/backend/settings.py:117).

### A02-03 — CORS permisivo si falta la variable — Medio

Si `CORS_ALLOWED_ORIGINS` no está definido, se habilitan varios orígenes de localhost y una IP histórica, con credenciales permitidas. Producción debe fallar al arrancar si la lista no está definida.

- [`CORS_ALLOWED_ORIGINS`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/backend/settings.py:207).

### A02-04 — El chequeo `--deploy` falla en local — Informativo

`manage.py check --deploy` informó seis advertencias porque se ejecutó intencionadamente sobre `.env.local`: `DEBUG=true`, HTTP y cookies no secure. No es evidencia de fallo en producción. Debe incorporarse un chequeo separado con variables de producción no secretas o en CI.

### Controles A02 presentes

- Producción configura por defecto HTTPS, HSTS, `nosniff`, frame denial y referrer policy: [`settings.py`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/backend/settings.py:272).
- Nginx añade CSP, HSTS y cabeceras de protección: [`nginx`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/nginx/conf.d/aladino.conf:14).
- La separación local/producción está documentada en [`RUNBOOK_ENVIRONMENTS.md`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/RUNBOOK_ENVIRONMENTS.md:1).

---

## A03 — Software Supply Chain Failures

### A03-01 — Dependencias frontend vulnerables — Alto

`npm audit --omit=dev` detectó seis vulnerabilidades: tres altas y tres moderadas.

| Dependencia | Severidad | Riesgo informado por npm |
|---|---|---|
| Next.js 15.5.24 | Moderada | Cache poisoning de SSG/ISR. |
| PostCSS transitivo | Alta | XSS, lectura de archivos y traversal mediante source maps. |
| Quill / react-quill | Moderada | XSS. |
| Sharp | Alta | Vulnerabilidad en librsvg. |
| source-map-js | Alta | Denegación de servicio del event loop. |

- Dependencias: [`package.json`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/frontend/package.json:1).
- Lockfile existente: [`package-lock.json`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/frontend/package-lock.json).
- La actualización sugerida por npm para Next es `15.5.27`; debe probarse antes de aplicar, sin usar `--force` a ciegas.

### A03-02 — CI no ejecuta SCA ni el frontend — Medio

CI instala Python y corre `manage.py test`, pero no ejecuta `npm ci`, lint/build/typecheck frontend, `npm audit`, `pip-audit`, generación SBOM ni escaneo de imagen.

- [`ci.yml`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/.github/workflows/ci.yml:51).

### A03-03 — Acciones e imágenes base no fijadas por digest — Medio

Las GitHub Actions se referencian por etiquetas y las imágenes Docker por tags mutables.

- [`actions/checkout@v4` y `setup-python@v5`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/.github/workflows/ci.yml:51).
- [`appleboy/ssh-action@v1.2.5`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/.github/workflows/deploy.yml:27).
- [`python:3.12-slim`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/Dockerfile:2), [`nginx:1.25-alpine`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/nginx/Dockerfile:1), [`postgres:15` y `redis:7.4-alpine`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/docker-compose.prod.yml:60).

---

## A04 — Cryptographic Failures

### A04-01 — Copia de base de datos local sin política de cifrado demostrable — Medio

Existe un dump operativo local ignorado por Git. No se encontró expuesto desde Nginx, pero el reposo, permisos de Windows, retención y respaldo cifrado no están documentados.

- [`backups/pre_operational_purge_2026-08-10.dump`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/backups/pre_operational_purge_2026-08-10.dump).

### A04-02 — Archivos de firma públicos — Medio

Es el mismo problema A01-03 con impacto de confidencialidad: las firmas y posibles adjuntos se sirven sin cifrado de aplicación ni autorización individual.

### Controles A04 presentes

- `.env` y `.env.local` no están versionados; el análisis de archivos Git no halló claves, dumps ni credenciales rastreadas.
- Sesiones con Redis, cookie HTTP-only y cookie de producción con prefijo `__Host-`: [`settings.py`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/backend/settings.py:162).
- Contraseñas usan el sistema de hashing de Django; no se detectó almacenamiento de contraseñas en texto plano en modelos o serializers revisados.

---

## A05 — Injection

### A05-01 — HTML sin sanitizar en frontend — Alto, requiere prueba controlada

Comentarios y conclusiones de reportes se persisten desde la interpretación y se insertan mediante `dangerouslySetInnerHTML`. No se detectó DOMPurify, `sanitize-html`, Bleach ni otra sanitización entre origen y presentación.

- Entrada persistida: [`save_interpretation_sample`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/resultado/api/views/index.py:2828).
- Modelo de reporte: [`comentarios` y `conclusiones`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/reporte/api/models/index.py:52).
- Vistas afectadas: [`DocumentsListPage.jsx`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/frontend/src/features/documents/presentation/pages/DocumentsListPage.jsx:238), [`ReportTemplateEditorPage.jsx`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/frontend/src/features/documents/presentation/pages/ReportTemplateEditorPage.jsx:756), y sus variantes `.js`.

**Remediación:** renderizar texto normal; si se necesita HTML limitado, sanearlo en servidor y cliente con una allowlist estricta. Probar con una cuenta de laboratorio antes de marcarlo como explotable.

### A05-02 — SSRF en generador PDF — Alto, requiere prueba controlada

El request de generación acepta `firma_ruta`. Si el recurso no existe en storage local, se conserva como URL; el callback de xhtml2pdf permite explícitamente recursos `http://` y `https://`.

- Entrada: [`_create_from_interpretation`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/reporte/api/views/index.py:559).
- Render del atributo `src`: [`globalreport.html`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/media/templates/globalreport.html:551).
- Acceso remoto: [`fetch_resources`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/reporte/api/views/index.py:1435).

**Remediación:** aceptar únicamente paths de storage con prefijo permitido y resolverlos localmente; bloquear URLs, IPs privadas y redirecciones salientes.

### A05-03 — Carga de firma confía en MIME declarado y carpeta controlada por cliente — Medio, requiere prueba controlada

La ruta acepta todo `image/*`, conserva la extensión suministrada y acepta el parámetro `folder`. No verifica magic bytes ni restringe el directorio a `firmas`.

- [`upload_signature`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/reporte/api/views/index.py:1021).

El storage de Django puede rechazar traversal; por eso no se declara traversal confirmado. SVG u otros formatos de imagen y el servicio público de `/media/` deben validarse en una prueba controlada.

### A05-04 — Importadores Excel sin límites homogéneos — Medio

El importador de lotes sí limita tamaño a 10 MB y 5.000 filas. Los importadores de resultados y matrices técnicas cargan directamente con `openpyxl` sin el mismo límite de tamaño/filas/hojas.

- Control correcto: [`validate_uploaded_workbook_file`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/muestras/api/views/sampleBatchExcel/index.py:254).
- Resultados sin límite equivalente: [`_parse_result_excel`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/resultado/api/views/index.py:2317).
- Configuración técnica: [`import_excel`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/misc/api/views/dynamicTechnicalConfig/index.py:256).

### Control A05 presente

No se encontraron consultas SQL crudas de aplicación (`raw`, `extra` o `cursor.execute` con entrada de request) fuera de migraciones. Las consultas revisadas usan ORM parametrizado.

---

## A06 — Insecure Design

### A06-01 — Aislamiento por tenant no es una regla única obligatoria — Medio

`HasSecurityPermission` comprueba permisos de acción, pero no implementa `has_object_permission` ni obliga a que cada queryset filtre por empresa. Los hallazgos A01-02 y A01-05 se originan precisamente en acciones que consultaron por ID directo.

- [`HasSecurityPermission`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/permissions.py:101).

**Remediación de diseño:** crear un mixin/manager de tenant obligatorio para recursos empresariales y pruebas parametrizadas de acceso entre dos empresas para cada endpoint de detalle/acción.

### A06-02 — Acciones de alto impacto no siguen un contrato uniforme — Medio

Generación de PDF, envío masivo de correo, carga de archivo y cambios de configuración dependen de checks en cada método. No hay un catálogo de amenazas ni una matriz que indique: permiso, tenant, auditoría, límite de frecuencia y validación por cada acción.

- Ejemplo de endpoint que solo pide autenticación: [`send_daily_digest`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/dashboard/api/views/index.py:29).

---

## A07 — Authentication Failures

### A07-01 — Corregido: recuperación revelaba cuentas y tenía expiración incoherente — Alto

Antes el endpoint respondía que el correo no existía y el método de envío eliminaba el token de 24 horas para crear otro con expiración de verificación. Ahora entrega la misma respuesta, limita solicitudes y conserva un solo token de recuperación con la expiración configurada.

- [`PasswordResetRequestSerializer`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/users/api/serializers/index.py:207).
- [`ForgotPasswordView`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/users/api/views/user/index.py:427).
- Limitador: [`session_security.py`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/users/api/session_security.py:57).
- Prueba: [`test_password_reset_does_not_enumerate_accounts_and_keeps_one_hour_policy`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/users/test_session_security.py:103).

### Controles A07 presentes

- Sesión de servidor en Redis, no JWT expuesto al navegador: [`LoginAV`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/users/api/views/user/index.py:174).
- CSRF obligatorio incluso en requests anónimos no seguros: [`StrictCsrfSessionAuthentication`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/users/api/session_security.py:10).
- Rate-limit de login, invalidación de sesiones y vida absoluta: [`middleware`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/backend/middleware.py:1).
- Registro público desactivado por defecto: [`UserRegistrationView`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/users/api/views/user/index.py:218).

### A07-02 — Pruebas pendientes de expiración real y bloqueo administrativo — Bajo

Existen pruebas de login, CSRF, logout, revocación y rate-limit. Aún faltan pruebas automatizadas de expiración por inactividad/vida absoluta y de invalidación al bloquear/desactivar un usuario.

---

## A08 — Software or Data Integrity Failures

### A08-01 — Despliegue no verifica el artefacto — Medio

El workflow se conecta por SSH, ejecuta `git reset --hard origin/master` y construye directamente en el servidor. No hay imagen promovida por digest, firma, verificación de procedencia ni SBOM.

- [`deploy.yml`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/.github/workflows/deploy.yml:27).

### A08-02 — El build ignora errores de lint de Next — Medio

Next tiene `ignoreDuringBuilds: true`; un lint que falle no bloquea el artefacto.

- [`next.config.js`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/frontend/next.config.js:8).

### A08-03 — Código ejecutado desde bind mount — Medio

Es también A02-01: rompe la integridad del artefacto de despliegue. Ver referencias de `docker-compose.prod.yml` allí.

---

## A09 — Security Logging and Alerting Failures

### A09-01 — Cobertura de auditoría desigual — Medio

Autenticación y varias operaciones de usuarios/lotes sí registran eventos, pero no se halló `audit_user_action` en generación, previsualización, publicación o envío de reportes. Son acciones con impacto y datos sensibles.

- Auditoría de login/logout: [`LoginAV` y `LogoutAV`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/users/api/views/user/index.py:204).
- Generación sin evento de auditoría: [`generate_from_interpretation`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/reporte/api/views/index.py:584).

### A09-02 — Sin evidencia de centralización, alertas o retención — Medio

No se halló configuración de agregador de logs, SIEM, alertas de fallos de login, envíos fallidos, cambios de rol o accesos denegados. Esto requiere revisión del host/plataforma, no solo código.

### A09-03 — Acceso a media no queda en log de Nginx — Bajo/medio

`/media/` usa `access_log off`, por lo que la exposición A01-03 no deja trazabilidad HTTP de Nginx.

- [`location /media/`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/nginx/conf.d/aladino.conf:75).

---

## A10 — Mishandling of Exceptional Conditions

### A10-01 — Excepciones internas devueltas a clientes — Medio

Hay varios handlers que incluyen `str(exc)`/`str(e)` en respuestas 5xx. Pueden revelar paths, configuración SMTP, detalles de storage o bibliotecas.

| Ruta | Ubicación |
|---|---|
| Sincronización de carpetas | [`SyncCompanyRootFolders`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/activesTree/api/views/index.py:75) |
| Árbol de activos | [`activesTree view`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/activesTree/api/views/activesTree/index.py:55) |
| Listado/creación de muestras | [`MuestraViewSetList`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/muestras/api/views/muestras/index.py:91) |
| Exportación y envío de reportes | [`ReporteViewSet`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/reporte/api/views/index.py:905) |
| Lectura de firma/PDF | [`ReporteViewSet`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/reporte/api/views/index.py:1018) |
| Importador técnico | [`import_excel`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/apps/misc/api/views/dynamicTechnicalConfig/index.py:267) |

**Remediación:** log interno con un ID de correlación y respuesta genérica al usuario; nunca enviar la excepción original.

### A10-02 — Procesamiento de archivos con recursos no acotados — Medio

Los importadores Excel señalados en A05-04 pueden consumir memoria o CPU excesiva con archivos complejos. Añadir límites de tamaño, filas, hojas y tiempo, y procesar en cola si el uso crece.

---

## Pruebas y comprobaciones ejecutadas

| Comprobación | Resultado |
|---|---|
| Salud local API | `200 {"status":"ok","database":"ok"}` |
| Sesiones, CSRF, recuperación y aislamiento de reportes | `22 passed` con pytest |
| SMTP local | envío de prueba aceptado por servidor (`SMTP_SENT=1`) |
| `npm audit --omit=dev` | 6 vulnerabilidades: 3 altas, 3 moderadas |
| `manage.py check --deploy` en `.env.local` | 6 advertencias esperables por modo HTTP/DEBUG local; no es evaluación de producción |
| Búsqueda de SQL crudo de aplicación | no encontrado fuera de migraciones |

## Orden recomendado de corrección

1. **Antes de producción:** A01-03 media privado, A05-01 XSS y A05-02 SSRF.
2. **Antes de asignar roles de empresa:** decidir/corregir A01-04 y A01-05, y crear pruebas multiempresa para todos los endpoints de acción.
3. **Próximo ciclo:** A03/A08 (actualizar dependencias, CI, imágenes inmutables y despliegue firmado).
4. **Robustez operativa:** A10 y A09 (errores genéricos, límites de importación, auditoría y alertas).
5. **Infraestructura:** cifrado/retención de backups y revisión externa de producción.

## Ejecución de remediación — 2026-10-14

Se aplicaron las correcciones que pueden resolverse en el repositorio y se conservaron los controles ya existentes.

| Área | Estado final | Evidencia para revisar |
|---|---|---|
| A01/A04: archivos privados | Corregido | [`private_media`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/backend/views.py), ruta Django en [`urls.py`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/backend/urls.py) y proxy autenticado en [`aladino.conf`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/nginx/conf.d/aladino.conf). |
| A01/A06: tenant y permisos | Corregido | Centro operacional usa permiso explícito y ya no otorga alcance global al administrador de empresa; `resolve-preview` y reportes filtran por empresa. |
| A02/A08: despliegue | Corregido | El compose de producción no monta el código fuente. Solo [`docker-compose.local.yml`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/docker-compose.local.yml) conserva el bind mount para desarrollo. Producción exige todas las variables sensibles en [`settings.py`](/C:/Users/Usuario/Documents/Proyectos/globalOil/developmentProduccion/development/backend/globalIsc/backend/settings.py). |
| A03: dependencias | Corregido en manifiesto | Se eliminó `react-quill`, se actualizó Next, PostCSS, Sharp y source-map-js. El audit de dependencias de runtime queda sin vulnerabilidades; el audit completo aún informa una cadena de desarrollo de `eslint-config-next`/`braces` que no tiene parche publicado compatible en el registro. No se ejecuta en producción. |
| A05: XSS, SSRF y cargas | Corregido | Las vistas ya no usan `dangerouslySetInnerHTML`; firmas son PNG/JPEG verificados, con tamaño y directorio fijo; PDF no recupera URLs externas; importaciones Excel limitan tamaño, hojas y filas. |
| A09: auditoría | Corregido en aplicación | Se añaden eventos para carga de firma, generación, lote, previsualización, aprobación, anulación y petición de digest. Centralización/SIEM, alertas y retención son controles de plataforma que requieren configurar el proveedor de producción. |
| A10: fallos | Corregido | Las rutas corregidas registran el detalle interno y ya no devuelven `str(exc)` en respuestas 5xx. |

### Limitaciones de infraestructura que no es seguro inventar desde código

- El cifrado, retención y restauración de copias de PostgreSQL requieren una clave gestionada y una política del operador. No se modificó ni borró ningún backup local.
- Un SIEM, alertas de seguridad y logs centralizados requieren un destino real (por ejemplo, proveedor cloud o servidor de logs) y credenciales de infraestructura. El código ya genera los eventos para enviarlos.
- Las versiones actualizadas del frontend están en `package.json` y `package-lock.json`. Como el servidor de desarrollo tiene `node_modules` abierto, debe reiniciarse e instalarse de forma limpia (`npm ci`) antes de probar el frontend con ese artefacto.

### Verificación posterior a la corrección

| Comprobación | Resultado |
|---|---|
| Compilación Python | Correcta (`python -m compileall`) |
| Sesiones, CSRF, recuperación y aislamiento de reportes | `22 passed` con pytest |
| Validación de compose local | Correcta (`docker compose ... config --quiet`) |
| Audit de runtime frontend | Sin vulnerabilidades después de eliminar ReactQuill y actualizar runtime; revisar el detalle anterior para la cadena exclusiva de desarrollo. |

## Fuentes OWASP

- [A01: Broken Access Control](https://top10.owasp.org/2025/A01_2025-Broken_Access_Control/)
- [A02: Security Misconfiguration](https://top10.owasp.org/2025/A02_2025-Security_Misconfiguration/)
- [A03: Software Supply Chain Failures](https://top10.owasp.org/2025/A03_2025-Software_Supply_Chain_Failures/)
- [A04: Cryptographic Failures](https://top10.owasp.org/2025/A04_2025-Cryptographic_Failures/)
- [A05: Injection](https://top10.owasp.org/2025/A05_2025-Injection/)
- [A06: Insecure Design](https://top10.owasp.org/2025/A06_2025-Insecure_Design/)
- [A07: Authentication Failures](https://top10.owasp.org/2025/A07_2025-Authentication_Failures/)
- [A08: Software or Data Integrity Failures](https://top10.owasp.org/2025/A08_2025-Software_or_Data_Integrity_Failures/)
- [A09: Security Logging and Alerting Failures](https://top10.owasp.org/2025/A09_2025-Security_Logging_and_Alerting_Failures/)
- [A10: Mishandling of Exceptional Conditions](https://top10.owasp.org/2025/A10_2025-Mishandling_of_Exceptional_Conditions/)

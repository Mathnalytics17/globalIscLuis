# Sesiones de producción con Redis

## Propósito

La aplicación usa sesiones de servidor almacenadas en Redis. El navegador no recibe ni guarda JWT, refresh tokens, roles ni credenciales de autorización. La única credencial de sesión es una cookie de identificador opaco; los datos y la autorización permanecen en Django y PostgreSQL.

## Flujo de autenticación

1. Al abrir la aplicación, el frontend solicita `GET /api/users/csrf/` y luego `GET /api/users/me/`.
2. Si la cookie de sesión es válida, entra directamente al dashboard. El formulario de login no se muestra durante la comprobación.
3. El login envía correo, contraseña y el encabezado `X-CSRFToken`. Django autentica al usuario, rota el identificador de sesión y guarda la sesión en Redis.
4. Las peticiones autenticadas usan la cookie `__Host-globaloil_session` en producción. JavaScript no puede leerla.
5. Logout, cambio/restablecimiento de contraseña, bloqueo y desactivación invalidan las sesiones mediante `session_epoch`.

## Controles implementados

- Redis privado: no publica el puerto 6379; requiere contraseña y usa AOF para persistencia.
- Sesión con `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/` y cookie host-only en producción.
- Expiración por inactividad de 30 minutos y límite absoluto de 8 horas, ambos configurables.
- CSRF obligatorio en peticiones inseguras, incluidas rutas públicas que modifican estado.
- Máximo de 5 intentos de login por IP y correo en 15 minutos; la respuesta no revela si el correo existe.
- Registro de eventos de login correcto, fallido, limitado, logout y cambio de contraseña en la auditoría existente.
- CSP, HSTS, protección contra clickjacking, `nosniff`, política de referencia y permisos del navegador en Nginx/Django.
- La autorización RBAC continúa siendo evaluada por el backend. La información de permisos que muestra el frontend es solo de interfaz.

## Variables de entorno

Copie `backend/.env.example` a un archivo `.env` gestionado fuera de Git. Nunca suba el archivo real, claves, contraseñas, certificados ni URLs con contraseñas.

| Variable | Uso | Producción |
| --- | --- | --- |
| `DJANGO_ENV` | Activa validaciones estrictas | `production` |
| `DJANGO_SECRET_KEY` | Firma criptográfica de Django | Cadena aleatoria larga y única |
| `POSTGRES_PASSWORD` | Acceso a PostgreSQL | Secreto único |
| `REDIS_PASSWORD` | Acceso al Redis privado | Secreto único, distinto de PostgreSQL |
| `REDIS_URL` | URL de Redis usada por Django | `redis://:CLAVE@redis:6379/0` |
| `CACHE_KEY_PREFIX` | Aísla claves por entorno | Por ejemplo `globaloil_prod` |
| `SESSION_COOKIE_AGE` | Inactividad máxima en segundos | `1800` |
| `SESSION_ABSOLUTE_AGE` | Duración máxima de sesión en segundos | `28800` |
| `LOGIN_MAX_ATTEMPTS` | Intentos permitidos | `5` |
| `LOGIN_LOCKOUT_SECONDS` | Duración del bloqueo | `900` |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos por Django | Dominio productivo exacto |
| `CORS_ALLOWED_ORIGINS` y `CSRF_TRUSTED_ORIGINS` | Orígenes de navegador permitidos | URL HTTPS exacta |
| `TRUST_X_FORWARDED_PROTO` y `TRUST_X_FORWARDED_FOR` | Confianza en el Nginx propio | `true` solo detrás del proxy administrado |

Genere secretos en una máquina segura, por ejemplo con `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Cambiar `DJANGO_SECRET_KEY`, `REDIS_PASSWORD` o la clave de sesión obliga a invalidar sesiones y debe planearse como una ventana de mantenimiento.

## Despliegue

1. Complete las variables reales en el gestor de secretos del servidor; no las copie a este repositorio.
2. Construya imágenes con las dependencias actualizadas y ejecute migraciones, incluida `users.0011_user_session_epoch`.
3. Levante `docker compose -f backend/docker-compose.prod.yml up -d --build` desde el directorio `backend`.
4. Confirme que Redis no está expuesto públicamente y que el healthcheck responde.
5. Pruebe el checklist siguiente antes de habilitar tráfico general.

## Desarrollo local

Producción y desarrollo local no deben compartir un volumen Docker. Para crear una base local nueva, copie `.env.local.example` a `.env.local` y ejecute:

```powershell
docker compose --project-name globaloil-local --env-file .env.local -f docker-compose.prod.yml -f docker-compose.local.yml up --build db redis web daphne
```

El nombre de proyecto crea volúmenes locales separados. PostgreSQL queda disponible únicamente en `localhost:5433` para pgAdmin; dentro de Docker, el backend sigue conectándose a `db:5432`. No incluya Nginx en ese comando local porque sus certificados Let’s Encrypt pertenecen al servidor de producción.

## Checklist de aceptación

- Iniciar sesión y recargar: entra al dashboard sin mostrar login.
- Abrir una ventana privada: solo allí aparece el login.
- Cerrar sesión: `/api/users/me/` devuelve 401 y la cookie deja de funcionar.
- Esperar inactividad o superar la vida absoluta: se requiere login nuevamente.
- Cambiar contraseña, bloquear o desactivar un usuario: sus otras sesiones quedan invalidadas.
- Enviar un POST sin `X-CSRFToken`: devuelve 403.
- Fallar seis accesos: recibe 429 sin confirmar si el correo existe.
- Revisar auditoría: existen eventos `auth.login_succeeded`, `auth.login_failed`, `auth.login_rate_limited`, `auth.logout` y `auth.password_changed`.

## Pruebas automatizadas

La prueba manual sigue siendo necesaria para la interfaz y para HTTPS/Nginx. El comportamiento del backend se cubre con `pytest`, una base de datos de pruebas independiente (`test_globaliscdb`) y una caché en memoria aislada; por tanto, las pruebas no usan ni eliminan sesiones del Redis de ejecución:

```powershell
docker exec backend pytest apps/users/test_session_security.py --reuse-db -q
```

La suite verifica que el login devuelve solo el usuario y una sesión de servidor, que una API sin sesión responde `401`, que un POST sin CSRF responde `403`, que el logout y la revocación invalidan la sesión, y que el sexto intento fallido recibe `429` sin enumerar usuarios.

## Operación y mantenimiento

- Monitorice disponibilidad, memoria y evicciones de Redis; una pérdida de Redis cierra sesiones, no concede acceso.
- Mantenga Redis en red privada y limite su acceso al backend. No use `ports: "6379:6379"`.
- Revise dependencias y actualice Django a una versión soportada antes del siguiente despliegue de producción.
- No se integra Google ni OAuth en este diseño.

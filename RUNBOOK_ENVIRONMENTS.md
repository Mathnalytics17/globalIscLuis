# Entornos locales y producción

Hay dos archivos de variables locales, ambos ignorados por Git:

- `.env`: producción. Contiene el dominio público, cookies seguras y las credenciales reales de SMTP. No se usa para pruebas locales.
- `.env.local`: desarrollo Docker. Usa `localhost`, cookies no seguras solo para HTTP local y la base Docker publicada en el puerto `5433`.

`docker-compose.local.yml` es un *override*, no un compose independiente. Para iniciar pruebas locales desde la carpeta `backend`, usa siempre:

```powershell
docker compose -p globaloil-local --env-file .env.local -f docker-compose.prod.yml -f docker-compose.local.yml up -d --build web daphne
```

Para detenerlo:

```powershell
docker compose -p globaloil-local --env-file .env.local -f docker-compose.prod.yml -f docker-compose.local.yml down
```

La base PostgreSQL continúa dentro del contenedor `postgres`; pgAdmin debe conectarse a `localhost:5433`. No publiques Redis.

Para producción se usa únicamente el compose base y el archivo `.env`:

```powershell
docker compose --env-file .env -f docker-compose.prod.yml up -d --build
```

## Limpieza de Docker en producción

Los despliegues automáticos eliminan los contenedores huérfanos del proyecto y,
al terminar correctamente, liberan contenedores detenidos, imágenes sin uso y
caché de construcción con más de siete días. Nunca ejecutan `docker volume
prune`: `postgres_data`, `redis_data` y los archivos de medios son datos
persistentes.

Si el servidor necesita conservar más o menos caché de Docker, defina
`DOCKER_PRUNE_UNTIL` en el entorno del usuario de despliegue con un valor válido
de duración Docker, por ejemplo `336h` para catorce días. No use una política de
pruning de volúmenes como parte del CD.

No combines `.env` y `.env.local`. Docker inyecta el archivo indicado antes de iniciar Django; Django no debe cargar otro archivo de forma implícita cuando ya recibe `DJANGO_ENV`.

## Correo

`.env.local` usa `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`, por lo que los correos locales se envían con las credenciales SMTP configuradas. Para depurar sin enviar correos reales, cambie temporalmente ese valor a `django.core.mail.backends.console.EmailBackend` y reinicie `web` y `daphne`.

El flujo de recuperación responde igual para correos existentes e inexistentes, limita solicitudes y usa `PASSWORD_RESET_TOKEN_EXPIRY_HOURS`.

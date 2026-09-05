# Despliegue de producción

## Requisitos

- Python 3.12 y las dependencias de `requirements.txt` instaladas en un entorno virtual.
- Node.js compatible con Next.js 14 y dependencias instaladas con `npm ci`.
- PostgreSQL accesible desde el backend.
- Volumen persistente o almacenamiento de objetos para `MEDIA_ROOT`. Las firmas y reportes no deben depender del disco efímero del contenedor.
- Proxy HTTPS que preserve el encabezado `X-Forwarded-Proto`.

## Variables mínimas del backend

Copiar `.env.example` al gestor de secretos del servidor. En producción son obligatorias, como mínimo:

- `DJANGO_ENV=production`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `CORS_ALLOWED_ORIGINS`
- credenciales `DB_*`
- credenciales de correo

No se debe subir un archivo `.env` real al repositorio.

## Verificación previa

Desde `backend/globalIsc` en el VPS Linux:

```bash
source ../venv/bin/activate
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py test
```

Desde `frontend`:

```bash
npm ci
npm run verify
```

## Publicación

1. Crear una copia de seguridad de PostgreSQL y del almacenamiento de medios.
2. Ejecutar `python manage.py migrate --noinput`.
3. Sincronizar permisos y roles con `python manage.py seed_access_baseline`.
4. Ejecutar `python manage.py collectstatic --noinput` si el proxy no sirve los estáticos desde otra etapa.
5. Construir el frontend con `npm run build` y ejecutarlo como servicio systemd con `npm start`.
6. Ejecutar Django mediante Gunicorn administrado por systemd; no usar `runserver`.
7. Verificar salud, login, carga de resultados, revisión, interpretación, generación y descarga de reportes.

Ejemplo de proceso backend, ejecutado desde `backend/globalIsc` con el entorno virtual activo:

```bash
gunicorn backend.wsgi:application \
  --bind 127.0.0.1:8000 \
  --workers 3 \
  --timeout 120
```

Gunicorn y Next.js deben quedar detrás de Nginx con HTTPS. Nginx debe servir los archivos estáticos y los medios persistentes, o delegarlos a un almacenamiento de objetos. Los comandos anteriores son referencias para las unidades systemd; no deben mantenerse mediante una terminal SSH abierta.

## Actualización desde la versión anterior

No conecte por primera vez el código nuevo directamente a la única copia de la base de producción.

1. Respaldar PostgreSQL y `MEDIA_ROOT` antes de detener la versión anterior.
2. Restaurar esos respaldos en un ambiente de ensayo con la misma versión de PostgreSQL.
3. Desplegar allí el código nuevo y ejecutar `migrate --noinput`.
4. Ejecutar `seed_access_baseline` para completar roles y permisos sin duplicarlos.
5. Probar el inicio de sesión y el aislamiento entre empresas con las cuentas indicadas abajo.
6. Si no se conservarán los datos operativos históricos, revisar primero `purge_operational_data --dry-run` y ejecutar el borrado solo después de aprobar sus conteos.
7. Repetir el procedimiento en producción dentro de una ventana de mantenimiento y conservar el respaldo hasta terminar las pruebas de humo.

## Reinicio operativo controlado

Para conservar pruebas, límites, catálogos, empresas, usuarios, roles y permisos, pero eliminar lotes, muestras, resultados y reportes:

```bash
python manage.py purge_operational_data --dry-run
python manage.py purge_operational_data --yes --include-security-transients --delete-files
```

No utilice `reset_globaloil_flow` para una actualización de producción: ese comando también reemplaza la configuración técnica por datos de ejemplo.

## Escenario de demostración multiempresa

El comando es idempotente: se puede ejecutar nuevamente para sincronizar los roles sin duplicar cuentas. La contraseña debe venir del gestor de secretos y no del repositorio.

```bash
export DEMO_DEFAULT_PASSWORD='una-clave-temporal-segura'
python manage.py seed_access_baseline --with-demo-accounts
unset DEMO_DEFAULT_PASSWORD
```

Use `--reset-passwords` solamente cuando se quiera restablecer deliberadamente las contraseñas de las cuentas existentes. Antes de entregar acceso al cliente, cambie la contraseña temporal y configure el correo real de cada cuenta.

Las cuentas creadas cubren estos escenarios:

| Cuenta | Empresa | Escenario |
| --- | --- | --- |
| `admin.global@globaloil.demo` | Global Oil | Administración global completa |
| `laboratorio@globaloil.demo` | Global Oil | Ingreso y gestión de laboratorio |
| `revisor@globaloil.demo` | Global Oil | Revisión e interpretación |
| `admin@minera.demo` | Empresa Minera Demo | Administración de una empresa cliente |
| `consulta@minera.demo` | Empresa Minera Demo | Consulta del cliente |
| `muestras@minera.demo` | Empresa Minera Demo | Carga de muestras del cliente |
| `admin@taller.demo` | Taller Demo | Segunda empresa para comprobar aislamiento |
| `lectura@taller.demo` | Taller Demo | Acceso de solo lectura |

Los dominios `.demo` son deliberadamente no entregables. Si se van a probar notificaciones reales, cambie cada correo por una dirección controlada de prueba antes de enviar mensajes.

## Reversión

Conservar la imagen anterior, el respaldo de base de datos y el respaldo de medios hasta completar las pruebas de humo. Las migraciones destructivas requieren un procedimiento de reversión específico antes de ejecutarse.

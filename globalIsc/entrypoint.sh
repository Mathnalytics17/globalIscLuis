#!/bin/sh

set -e

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    echo "Applying committed database migrations..."
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
fi

exec "$@"

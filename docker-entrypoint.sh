#!/bin/sh
set -e

# Solo ejecutar migraciones y collectstatic en el contenedor principal (Web)
# Evita condición de carrera (race condition) con Celery Worker y Beat
if [ "$1" = "uwsgi" ] || [ "$1" = "python" ]; then
    echo "=== Iniciando tareas de despliegue en contenedor principal ==="
    # Migrations (safe: solo aplica pendientes)
    python manage.py migrate --noinput || true

    # Collect static files (--clear elimina huérfanos)
    python manage.py collectstatic --noinput --clear || true
    echo "=== Tareas completadas ==="
else
    echo "=== Iniciando servicio secundario ($1) ==="
fi

exec "$@"

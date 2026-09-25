#!/bin/sh
set -e

# Solo ejecutar migraciones y collectstatic en el contenedor principal (Web)
# Evita condición de carrera (race condition) con Celery Worker y Beat
if [ "$1" = "uwsgi" ] || [ "$1" = "python" ]; then
    echo "=== Iniciando tareas de despliegue en contenedor principal ==="
    # POR QUÉ: Fail-closed. Si las migraciones fallan, abortar arranque para evitar operar con schema corrupto (SEC-INF-004)
    python manage.py migrate --noinput

    # Collect static files (--clear elimina huérfanos)
    python manage.py collectstatic --noinput --clear
    echo "=== Tareas completadas ==="
else
    echo "=== Iniciando servicio secundario ($1) ==="
fi

exec "$@"

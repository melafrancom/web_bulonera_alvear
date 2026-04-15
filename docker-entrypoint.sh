#!/bin/sh
set -e

# Migrations (safe: solo aplica pendientes)
python manage.py migrate --noinput || true

# Collect static files (--clear elimina huérfanos)
python manage.py collectstatic --noinput --clear || true

exec "$@"

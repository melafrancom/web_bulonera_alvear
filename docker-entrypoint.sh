#!/bin/sh
set -e

# Allow container startup even if DB is temporarily unavailable.
python manage.py collectstatic --noinput || true

exec "$@"

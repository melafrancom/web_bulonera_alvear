# REGLA: Configuración aislada de Staging para Pruebas de Carga (Load Testing)
# POR QUÉ: Permite evaluar la concurrencia real de uWSGI con DEBUG=False y conexiones locales,
# asegurando que ninguna credencial real de producción ni despacho externo (SMTP, Meta CAPI) sea utilizado.

from .base import *

DEBUG = False

# Restringido estrictamente a interfaces locales e internas de Docker (sin comodín '*')
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'bulonera-web', 'testserver']

# Base de datos exclusivamente local (contenedor MariaDB de desarrollo)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'buloneraalvearDB_dev',
        'USER': 'bulonera_dev',
        'PASSWORD': 'bulonera_dev_password',
        'HOST': 'db_mariadb',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
            'collation': 'utf8mb4_spanish_ci',
            'init_command': "SET NAMES 'utf8mb4' COLLATE 'utf8mb4_spanish_ci';",
        }
    }
}

# Seguridad HTTP relajada para pruebas directas en puerto 8002 sin SSL
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

# Neutralización absoluta de servicios y notificaciones externas
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
META_PIXEL_ENABLED = False
META_PIXEL_ID = ''
META_CAPI_TOKEN = ''
INDEXNOW_API_KEY = ''
GOOGLE_MAPS_EMBED_KEY = ''
GOOGLE_PLACE_ID = ''

# Modo Eager en Celery: resuelve tareas síncronamente en memoria
# POR QUÉ: Evita que Django acumule mensajes en la cola Redis DB 0 sin workers activos
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = 'redis://bulonera_web_redis:6379/15'
CELERY_RESULT_BACKEND = 'redis://bulonera_web_redis:6379/15'

# Caché activa en Redis local (DB 2) para simular el comportamiento de producción
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://bulonera_web_redis:6379/2',
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {'max_connections': 50},
        }
    }
}

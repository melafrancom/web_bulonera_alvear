"""
Deep Health Check Endpoint para monitoreo de infraestructura y contenedores.

QUÉ:
    Verifica conectividad real a MariaDB y Redis Cache.

POR QUÉ:
    El healthcheck anterior (`/`) solo evaluaba que el home cargara.
    Un home cacheado puede retornar 200 incluso con la BD caída.

CÓMO:
    1. Ejecuta 'SELECT 1' sobre MariaDB.
    2. Realiza set/get de una llave temporal en Redis.
    3. Retorna HTTP 200 si ambos responden, HTTP 503 si MariaDB falla.
"""
import logging
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger('django')


def deep_health_check(request):
    """Endpoint profundo de estado del sistema: /api/health/"""
    checks = {}
    healthy = True

    # 1. Verificar MariaDB
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks['database'] = 'ok'
    except Exception as e:
        checks['database'] = f'error: {type(e).__name__}'
        healthy = False
        logger.error(f'Health check falló en DB: {e}')

    # 2. Verificar Redis (Caché)
    try:
        cache.set('_health_check', 'ok', timeout=5)
        result = cache.get('_health_check')
        if result == 'ok':
            checks['cache'] = 'ok'
        else:
            checks['cache'] = 'degraded'
    except Exception as e:
        checks['cache'] = f'error: {type(e).__name__}'
        logger.warning(f'Health check falló en Caché: {e}')

    overall_status = 'healthy'
    if checks.get('cache') != 'ok':
        overall_status = 'degraded'
    if not healthy:
        overall_status = 'unhealthy'

    status_code = 200 if healthy else 503
    return JsonResponse(
        {
            'status': overall_status,
            'service': 'bulonera_web',
            'checks': checks,
        },
        status=status_code,
    )

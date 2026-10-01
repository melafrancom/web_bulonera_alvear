"""
Utilidades compartidas de BULONERA WEB.

Funciones transversales usadas por múltiples apps (account, contact, etc.)
para evitar duplicación de código (DRY).
"""
import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)


def get_client_ip(request) -> str:
    """
    Extrae la IP real del cliente considerando el proxy reverso (OLS).

    POR QUÉ: Detrás de OpenLiteSpeed, REMOTE_ADDR es siempre 127.0.0.1.
    La IP real viaja en el header X-Forwarded-For (primer valor de la cadena).
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


class RateLimitExceeded(Exception):
    """Lanzada cuando una IP excede el límite de intentos permitidos."""
    def __init__(self, ip: str, limit: int, scope: str):
        self.ip = ip
        self.limit = limit
        self.scope = scope
        super().__init__(f"Rate limit ({scope}): {limit} intentos excedidos para IP {ip}")


def check_rate_limit(client_ip: str, scope: str, limit: int, timeout: int) -> None:
    """
    Verifica si una IP ha excedido el límite de intentos usando Django Cache/Redis.

    Qué: Función genérica de rate limiting basada en caché atómica.
    Por qué: Las vistas HTML no tienen protección de DRF Throttling.
             Centralizar la lógica evita duplicación entre login, register y forgotPassword.

    Args:
        client_ip: Dirección IP del cliente.
        scope: Identificador del contexto (ej: 'login', 'register', 'forgot_password').
        limit: Número máximo de intentos permitidos dentro del timeout.
        timeout: Ventana de tiempo en segundos.

    Raises:
        RateLimitExceeded: Si la IP superó el límite en la ventana de tiempo.
    """
    if not client_ip:
        return

    key = f"rate_limit:{scope}:{client_ip}"
    cache.add(key, 0, timeout=timeout)
    count = cache.incr(key)
    if count > limit:
        logger.warning("Rate limit excedido (scope=%s, ip=%s, intentos=%s)", scope, client_ip, count)
        raise RateLimitExceeded(client_ip, limit, scope)

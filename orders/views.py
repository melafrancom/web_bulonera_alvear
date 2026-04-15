"""
Orders Views - Compatibility Layer

DEPRECATED: Este archivo mantiene compatibilidad hacia atrás.
Las vistas ahora están organizadas en:
- orders.web.views (vistas HTML tradicionales)
- orders.api.views (API REST con DRF)

Usar las importaciones directas desde los módulos correspondientes.
"""
from orders.web.views import (
    place_order as place_orders,
    payments,
    order_complete,
    whatsapp_redirect
)

__all__ = [
    'place_orders',
    'payments',
    'order_complete',
    'whatsapp_redirect'
]

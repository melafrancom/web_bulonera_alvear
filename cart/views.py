"""
Cart Views - Compatibility Layer

DEPRECATED: Este archivo mantiene compatibilidad hacia atrás.
Las vistas ahora están organizadas en:
- cart.web.views (vistas HTML tradicionales)
- cart.api.views (API REST con DRF)

Usar las importaciones directas desde los módulos correspondientes.
"""
from cart.web.views import (
    cart_view as cart,
    add_cart,
    remove_cart,
    remove_cart_item,
    get_cart_data,
    checkout
)

# Mantener función _cart_id para compatibilidad
from cart.services import CartService

def _cart_id(request):
    """DEPRECATED: Usar CartService.get_or_create_cart_id(request)"""
    return CartService.get_or_create_cart_id(request)

__all__ = [
    'cart',
    'add_cart',
    'remove_cart',
    'remove_cart_item',
    'get_cart_data',
    'checkout',
    '_cart_id'
]

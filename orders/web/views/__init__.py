"""Orders Web Views Package"""
from .views import (
    place_order,
    payments,
    order_complete,
    whatsapp_redirect,
    orders_index
)

__all__ = [
    'place_order',
    'payments',
    'order_complete',
    'whatsapp_redirect',
    'orders_index'
]


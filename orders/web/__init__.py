"""Orders Web Package"""
from .views import (
    place_order,
    payments,
    order_complete,
    whatsapp_redirect
)
from .forms import OrderForm

__all__ = [
    'place_order',
    'payments',
    'order_complete',
    'whatsapp_redirect',
    'OrderForm'
]

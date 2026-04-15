"""
Cart URLs - Compatibility Layer

DEPRECATED: Este archivo mantiene compatibilidad hacia atrás.
Las URLs ahora están organizadas en:
- cart.web.urls (URLs para vistas HTML tradicionales)
- cart.api.urls (URLs para API REST con DRF)

Configuración recomendada en web_bulonera/urls.py:
    path('cart/', include('cart.web.urls', namespace='cart_web')),
    path('api/v1/', include('cart.api.urls', namespace='cart_api')),
"""
from cart.web.urls import urlpatterns, app_name

__all__ = ['urlpatterns', 'app_name']
"""
Orders URLs - Compatibility Layer

DEPRECATED: Este archivo mantiene compatibilidad hacia atrás.
Las URLs ahora están organizadas en:
- orders.web.urls (URLs para vistas HTML tradicionales)
- orders.api.urls (URLs para API REST con DRF)

Configuración recomendada en web_bulonera/urls.py:
    path('orders/', include('orders.web.urls', namespace='orders_web')),
    path('api/v1/', include('orders.api.urls', namespace='orders_api')),
"""
from orders.web.urls import urlpatterns, app_name

__all__ = ['urlpatterns', 'app_name']
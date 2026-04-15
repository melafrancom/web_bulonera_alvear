"""
Contact URLs - Compatibility Layer

DEPRECATED: Este archivo mantiene compatibilidad hacia atrás.
Las URLs ahora están organizadas en:
- contact.web.urls (URLs para vistas HTML tradicionales)
- contact.api.urls (URLs para API REST con DRF)

Configuración recomendada en web_bulonera/urls.py:
    path('contact/', include('contact.web.urls', namespace='contact_web')),
    path('api/v1/contact/', include('contact.api.urls', namespace='contact_api')),
"""
from contact.web.urls import urlpatterns, app_name

__all__ = ['urlpatterns', 'app_name']


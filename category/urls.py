"""
Category URLs - Compatibility Layer

DEPRECATED: Este archivo mantiene compatibilidad hacia atrás.
Las URLs ahora están organizadas en:
- category.api.urls (URLs para API REST con DRF)
- category.web.urls (URLs para vistas HTML - actualmente vacío)

La app category no tiene vistas web propias, solo provee datos vía:
- API REST
- Context processor (menu_links)

Configuración recomendada en web_bulonera/urls.py:
    path('api/v1/', include('category.api.urls', namespace='category_api')),
"""

# No hay URLs web para esta app
urlpatterns = []

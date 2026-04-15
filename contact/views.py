"""
Contact Views - Compatibility Layer

DEPRECATED: Este archivo mantiene compatibilidad hacia atrás.
Las vistas ahora están organizadas en:
- contact.web.views (vistas HTML tradicionales)
- contact.api.views (API REST con DRF)

Usar las importaciones directas desde los módulos correspondientes.
"""
from contact.web.views import contact_view, contact_success

__all__ = ['contact_view', 'contact_success']



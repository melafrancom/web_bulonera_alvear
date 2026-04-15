"""
Contact App

App para gestión de mensajes de contacto con soporte para múltiples canales
(email, WhatsApp).

Estructura:
- models.py: Modelo ContactOption
- services.py: Lógica de negocio (ContactService)
- api/: Capa API REST (DRF)
- web/: Capa de vistas HTML tradicionales
- tests/: Tests unitarios y de integración
"""

default_app_config = 'contact.apps.ContactConfig'

__all__ = []

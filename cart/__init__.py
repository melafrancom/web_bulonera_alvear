"""
Cart App

App para gestión del carrito de compras con soporte para usuarios
autenticados y anónimos.

Estructura:
- models.py: Modelos Cart y CartItem
- services.py: Lógica de negocio (CartService)
- context_processors.py: Context processor para contador del carrito
- api/: Capa API REST (DRF)
- web/: Capa de vistas HTML tradicionales
- tests/: Tests unitarios y de integración

Características:
- Soporte para usuarios autenticados y anónimos
- Gestión de variaciones de productos
- Fusión de carritos al hacer login
- Cálculo automático de precios (regular/oferta)
"""

default_app_config = 'cart.apps.CartConfig'

__all__ = []

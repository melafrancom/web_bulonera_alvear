"""
Orders App

App para gestión de órdenes, pagos y checkout con integración WhatsApp.

Estructura:
- models.py: Modelos Order, Payment, OrderProduct
- services.py: Lógica de negocio (OrderService, PaymentService, CheckoutService, WhatsAppService)
- api/: Capa API REST (DRF)
- web/: Capa de vistas HTML tradicionales
- tests/: Tests unitarios y de integración

Características:
- Proceso de checkout completo
- Múltiples métodos de pago
- Integración con WhatsApp para notificaciones
- Gestión de stock automática
- Emails de confirmación
"""

default_app_config = 'orders.apps.OrdersConfig'

__all__ = []

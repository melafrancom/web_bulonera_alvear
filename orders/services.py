"""
Orders App Services

Contiene la lógica de negocio para manejo de órdenes, pagos y checkout.
"""
import logging
import datetime
import urllib.parse
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from django.db import transaction
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

from .models import Order, Payment, OrderProduct
from cart.models import CartItem
from store.models import Product
from account.models import Account

logger = logging.getLogger(__name__)


class OrderService:
    """Servicio para manejo de órdenes"""
    
    @staticmethod
    def generate_order_number(order_id: int) -> str:
        """
        Genera un número de orden único basado en la fecha y el ID.
        
        Args:
            order_id: ID de la orden
            
        Returns:
            str: Número de orden en formato YYYYMMDD{id}
        """
        today = datetime.date.today()
        date_str = today.strftime("%Y%m%d")
        return f"{date_str}{order_id}"
    
    @staticmethod
    @transaction.atomic
    def create_order_from_cart(
        user: Account,
        form_data: Dict,
        cart_items: List[CartItem],
        ip_address: str = None
    ) -> Order:
        """
        Crea una orden desde los items del carrito.
        
        Args:
            user: Usuario que realiza la orden
            form_data: Datos del formulario de checkout
            cart_items: Items del carrito
            ip_address: Dirección IP del usuario
            
        Returns:
            Order: Orden creada
            
        Raises:
            ValueError: Si el carrito está vacío o hay datos inválidos
        """
        if not cart_items:
            raise ValueError("El carrito está vacío")
        
        # Calcular total
        total = sum(Decimal(str(item.sub_total)) for item in cart_items)
        
        # Crear orden
        order = Order.objects.create(
            user=user,
            first_name=form_data['first_name'],
            last_name=form_data['last_name'],
            phone=form_data['phone'],
            email=form_data['email'],
            address_line_1=form_data['address_line_1'],
            address_line_2=form_data.get('address_line_2', ''),
            country=form_data['country'],
            city=form_data['city'],
            state=form_data['state'],
            order_note=form_data.get('order_note', ''),
            order_total=float(total),
            ip=ip_address or ''
        )
        
        # Generar número de orden
        order.order_number = OrderService.generate_order_number(order.id)
        order.save()
        
        # Crear OrderProducts
        for cart_item in cart_items:
            order_product = OrderProduct.objects.create(
                order=order,
                user=user,
                product=cart_item.product,
                quantity=cart_item.quantity,
                purchase_price=cart_item.purchase_price,
                ordered=False
            )
            
            # Agregar variaciones si existen
            if cart_item.variation.exists():
                order_product.variation.set(cart_item.variation.all())
        
        logger.info(f"Orden {order.order_number} creada para usuario {user.id}")
        return order
    
    @staticmethod
    def get_user_orders(user: Account) -> List[Order]:
        """
        Obtiene todas las órdenes de un usuario.
        
        Args:
            user: Usuario
            
        Returns:
            List de Order ordenadas por fecha descendente
        """
        return Order.objects.filter(user=user).order_by('-created_at')
    
    @staticmethod
    def get_order_by_number(order_number: str, user: Account = None) -> Optional[Order]:
        """
        Obtiene una orden por su número.
        
        Args:
            order_number: Número de orden
            user: Usuario (opcional, para validar pertenencia)
            
        Returns:
            Order o None si no existe
        """
        try:
            if user:
                return Order.objects.get(order_number=order_number, user=user)
            return Order.objects.get(order_number=order_number)
        except Order.DoesNotExist:
            logger.warning(f"Orden {order_number} no encontrada")
            return None


class PaymentService:
    """Servicio para manejo de pagos"""
    
    @staticmethod
    @transaction.atomic
    def process_payment(
        user: Account,
        order: Order,
        payment_data: Dict
    ) -> Payment:
        """
        Procesa un pago y actualiza la orden.
        
        Args:
            user: Usuario que realiza el pago
            order: Orden a pagar
            payment_data: Datos del pago (payment_id, method, status)
            
        Returns:
            Payment: Pago creado
            
        Raises:
            ValueError: Si la orden ya fue pagada o datos inválidos
        """
        if order.is_ordered:
            raise ValueError("Esta orden ya fue pagada")
        
        # Crear pago
        payment = Payment.objects.create(
            user=user,
            payment_id=payment_data['payment_id'],
            payment_method=payment_data['payment_method'],
            amount_id=str(order.order_total),
            status=payment_data['status']
        )
        
        # Actualizar orden
        order.payment = payment
        order.is_ordered = True
        order.save()
        
        # Actualizar OrderProducts
        order_products = OrderProduct.objects.filter(order=order)
        for order_product in order_products:
            order_product.payment = payment
            order_product.ordered = True
            order_product.save()
            
            # Actualizar stock del producto
            product = order_product.product
            product.stock -= order_product.quantity
            product.save()
        
        logger.info(f"Pago procesado para orden {order.order_number}")
        return payment
    
    @staticmethod
    def create_whatsapp_payment(user: Account, order: Order) -> Payment:
        """
        Crea un pago pendiente para WhatsApp.
        
        Args:
            user: Usuario
            order: Orden
            
        Returns:
            Payment: Pago creado con estado pendiente
        """
        payment = Payment.objects.create(
            user=user,
            payment_id=f"WA-{order.order_number}",
            payment_method="WhatsApp",
            amount_id=str(order.order_total),
            status="Pending"
        )
        
        order.payment = payment
        order.is_ordered = True
        order.save()
        
        logger.info(f"Pago WhatsApp creado para orden {order.order_number}")
        return payment


class CheckoutService:
    """Servicio para el proceso de checkout completo"""
    
    @staticmethod
    @transaction.atomic
    def complete_checkout(
        user: Account,
        form_data: Dict,
        ip_address: str = None
    ) -> Order:
        """
        Completa el proceso de checkout creando la orden.
        
        Args:
            user: Usuario
            form_data: Datos del formulario
            ip_address: IP del usuario
            
        Returns:
            Order: Orden creada
            
        Raises:
            ValueError: Si hay errores en el proceso
        """
        # Obtener items del carrito
        cart_items = CartItem.objects.filter(user=user, is_active=True)
        
        if not cart_items.exists():
            raise ValueError("El carrito está vacío")
        
        # Crear orden
        order = OrderService.create_order_from_cart(
            user=user,
            form_data=form_data,
            cart_items=cart_items,
            ip_address=ip_address
        )
        
        # Limpiar carrito
        cart_items.delete()
        
        logger.info(f"Checkout completado para orden {order.order_number}")
        return order
    
    @staticmethod
    def send_order_confirmation_email(order: Order) -> bool:
        """
        Envía email de confirmación de orden.
        
        Args:
            order: Orden
            
        Returns:
            bool: True si se envió exitosamente
        """
        try:
            mail_subject = 'Tu compra fue realizada!'
            body = render_to_string('orders/order_recieved_email.html', {
                'user': order.user,
                'order': order,
            })
            
            email = EmailMessage(
                subject=mail_subject,
                body=body,
                to=[order.email]
            )
            email.send()
            
            logger.info(f"Email de confirmación enviado para orden {order.order_number}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email para orden {order.order_number}: {e}")
            return False


class WhatsAppService:
    """Servicio para integración con WhatsApp"""
    
    @staticmethod
    def generate_order_message(order: Order) -> str:
        """
        Genera el mensaje de WhatsApp para una orden.
        
        Args:
            order: Orden
            
        Returns:
            str: Mensaje formateado para WhatsApp
        """
        message = f"""🛒 *Nueva Orden de Compra*

🆔 *ID de Orden:* {order.order_number}
👤 *Cliente:* {order.full_name()}
📞 *Teléfono:* {order.phone}
📧 *Email:* {order.email}
📍 *Dirección:* {order.address_line_1}, {order.city}, {order.state}

📦 *Productos Ordenados:*
"""
        
        # Obtener productos
        ordered_products = OrderProduct.objects.filter(order=order)
        for i, product_item in enumerate(ordered_products, 1):
            # Variaciones (si existen)
            variations = product_item.variation.all()
            var_str = ""
            if variations.exists():
                var_str = " - " + ", ".join([
                    f"{v.variation_category}: {v.variation_value}" 
                    for v in variations
                ])
            
            message += (
                f"{i}. {product_item.product.name} 📦 "
                f"(Cantidad: {product_item.quantity}) "
                f"💲 {product_item.purchase_price:.2f}{var_str}\n"
            )
        
        # Total
        message += f"\n💰 *Total de la Orden:* ${order.order_total:.2f}"
        
        return message
    
    @staticmethod
    def generate_whatsapp_link(order: Order) -> str:
        """
        Genera el link de WhatsApp para una orden.
        
        Args:
            order: Orden
            
        Returns:
            str: URL de WhatsApp con mensaje pre-cargado
        """
        message = WhatsAppService.generate_order_message(order)
        encoded_message = urllib.parse.quote(message)
        
        phone_number = getattr(settings, 'WHATSAPP_NUMBER', '')
        
        return f"https://wa.me/{phone_number}?text={encoded_message}"
    
    @staticmethod
    @transaction.atomic
    def process_whatsapp_order(order: Order) -> Tuple[Payment, str]:
        """
        Procesa una orden para pago por WhatsApp.
        
        Args:
            order: Orden
            
        Returns:
            Tuple[Payment, str]: Pago creado y link de WhatsApp
        """
        # Crear pago pendiente
        payment = PaymentService.create_whatsapp_payment(order.user, order)
        
        # Actualizar OrderProducts
        order_products = OrderProduct.objects.filter(order=order)
        for order_product in order_products:
            order_product.payment = payment
            order_product.ordered = True
            order_product.save()
            
            # Actualizar stock
            product = order_product.product
            product.stock -= order_product.quantity
            product.save()
        
        # Generar link
        whatsapp_link = WhatsAppService.generate_whatsapp_link(order)
        
        logger.info(f"Orden {order.order_number} procesada para WhatsApp")
        return payment, whatsapp_link

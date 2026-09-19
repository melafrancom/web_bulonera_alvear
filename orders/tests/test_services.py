"""
Tests para OrderService, PaymentService, CheckoutService.
"""
import pytest
from decimal import Decimal
from django.test import TestCase
from orders.models import Order, Payment, OrderProduct
from orders.services import OrderService, PaymentService, CheckoutService
from cart.models import CartItem


@pytest.mark.django_db
class TestOrderService:
    """Tests para OrderService."""

    def test_generate_order_number_format(self):
        """Genera número de orden en formato YYYYMMDD{id}"""
        order_number = OrderService.generate_order_number(order_id=123)
        # Verificar que comienza con YYYYMMDD
        import datetime
        today = datetime.date.today().strftime("%Y%m%d")
        assert order_number.startswith(today)
        assert '123' in order_number

    def test_create_order_from_cart_success(self, user, product):
        """Crea orden desde carrito correctamente"""
        from cart.models import Cart, CartItem
        
        # Crear CartItems
        cart = Cart.objects.create(cart_id=f'test-{user.id}')
        cart_item = CartItem.objects.create(
            cart=cart,
            user=user,
            product=product,
            quantity=2,
            is_active=True,
            purchase_price=product.price
        )
        
        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'phone': '1234567890',
            'email': user.email,
            'address_line_1': 'Calle Test 123',
            'address_line_2': 'Apt 4B',
            'country': 'Argentina',
            'city': 'Buenos Aires',
            'state': '1000',
            'order_note': 'Notas de la orden'
        }
        
        cart_items = CartItem.objects.filter(user=user)
        order = OrderService.create_order_from_cart(
            user=user,
            form_data=form_data,
            cart_items=cart_items,
            ip_address='127.0.0.1'
        )
        
        assert order.user == user
        assert order.first_name == 'Test'
        assert order.last_name == 'User'
        assert order.order_number is not None
        assert order.order_total > 0

    def test_create_order_empty_cart_raises_error(self, user):
        """Lanza ValueError si carrito está vacío"""
        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'phone': '1234567890',
            'email': user.email,
            'address_line_1': 'Test St',
            'country': 'Argentina',
            'city': 'CABA',
            'state': '1000'
        }
        
        with pytest.raises(ValueError, match="carrito está vacío"):
            OrderService.create_order_from_cart(
                user=user,
                form_data=form_data,
                cart_items=[],
                ip_address='127.0.0.1'
            )

    def test_get_user_orders_returns_list(self, user):
        """Obtiene lista de órdenes del usuario"""
        orders = OrderService.get_user_orders(user)
        assert isinstance(orders, list) or hasattr(orders, '__iter__')

    def test_get_order_by_number_success(self, user, product):
        """Obtiene orden por número"""
        from cart.models import Cart, CartItem
        
        # Crear CartItem
        cart = Cart.objects.create(cart_id=f'test-{user.id}')
        CartItem.objects.create(
            cart=cart,
            user=user,
            product=product,
            quantity=1,
            is_active=True,
            purchase_price=product.price
        )
        
        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'phone': '123',
            'email': user.email,
            'address_line_1': 'Test',
            'country': 'AR',
            'city': 'BA',
            'state': '1000'
        }
        cart_items = CartItem.objects.filter(user=user)
        created_order = OrderService.create_order_from_cart(user, form_data, cart_items)
        
        found = OrderService.get_order_by_number(created_order.order_number)
        assert found == created_order

    def test_get_order_by_number_not_found(self):
        """Retorna None si orden no existe"""
        found = OrderService.get_order_by_number('INEXISTENTE')
        assert found is None


@pytest.mark.django_db
class TestPaymentService:
    """Tests para PaymentService."""

    def test_process_payment_success(self, user, product):
        """Procesa un pago correctamente"""
        # Crear orden directamente sin ir por cart
        order = Order.objects.create(
            user=user,
            first_name='Test',
            last_name='User',
            phone='123',
            email=user.email,
            address_line_1='Test',
            country='AR',
            city='BA',
            state='1000',
            order_number='20240101001',
            order_total=100.0,
            is_ordered=False
        )
        
        # Procesar pago
        payment_data = {
            'payment_id': 'PAY123',
            'payment_method': 'Credit Card',
            'status': 'Completed'
        }
        payment = PaymentService.process_payment(user, order, payment_data)
        
        assert payment.payment_id == 'PAY123'
        assert order.is_ordered is True

    def test_process_payment_already_ordered_raises_error(self, user, product):
        """Lanza error si orden ya fue pagada"""
        order = Order.objects.create(
            user=user,
            first_name='Test',
            last_name='User',
            phone='123',
            email=user.email,
            address_line_1='Test',
            country='AR',
            city='BA',
            state='1000',
            order_number='20240101001',
            order_total=100.0,
            is_ordered=True  # Ya pagada
        )
        
        payment_data = {
            'payment_id': 'PAY123',
            'payment_method': 'Credit Card',
            'status': 'Completed'
        }
        
        with pytest.raises(ValueError, match="ya fue pagada"):
            PaymentService.process_payment(user, order, payment_data)

    def test_create_whatsapp_payment(self, user, product):
        """Crea pago WhatsApp con status Pending"""
        order = Order.objects.create(
            user=user,
            first_name='Test',
            last_name='User',
            phone='123',
            email=user.email,
            address_line_1='Test',
            country='AR',
            city='BA',
            state='1000',
            order_number='20240101001',
            order_total=100.0,
            is_ordered=False
        )
        
        payment = PaymentService.create_whatsapp_payment(user, order)
        
        assert payment.payment_method == 'WhatsApp'
        assert payment.status == 'Pending'
        assert 'WA-' in payment.payment_id


@pytest.mark.django_db
class TestCheckoutService:
    """Tests para CheckoutService."""

    def test_complete_checkout_success(self, user, product):
        """Completa checkout exitosamente"""
        # Crear CartItem
        from cart.models import Cart, CartItem
        cart = Cart.objects.create(cart_id=f'test-{user.id}')
        CartItem.objects.create(
            cart=cart,
            user=user,
            product=product,
            quantity=2,
            is_active=True
        )
        
        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'phone': '123',
            'email': user.email,
            'address_line_1': 'Test',
            'country': 'AR',
            'city': 'BA',
            'state': '1000'
        }
        
        order = CheckoutService.complete_checkout(user, form_data, ip_address='127.0.0.1')
        
        assert order is not None
        assert order.user == user
        # Verificar que carrito fue limpiado
        remaining_items = CartItem.objects.filter(user=user, is_active=True)
        assert remaining_items.count() == 0

    def test_complete_checkout_empty_cart_raises_error(self, user):
        """Lanza error si carrito está vacío"""
        form_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'phone': '123',
            'email': user.email,
            'address_line_1': 'Test',
            'country': 'AR',
            'city': 'BA',
            'state': '1000'
        }
        
        with pytest.raises(ValueError, match="carrito está vacío"):
            CheckoutService.complete_checkout(user, form_data)


@pytest.mark.django_db
class TestAtomicity:
    """AUD-ORD-NEW-001: Verificar atomicidad de is_ordered + stock."""

    def test_double_submit_raises_error(self, user, product):
        """Pagar una orden ya pagada lanza error."""
        order = Order.objects.create(
            user=user, first_name='Test', last_name='User',
            phone='123', email=user.email,
            address_line_1='Test', country='AR',
            city='BA', state='1000',
            order_number='20240101003', order_total=10.0,
            is_ordered=True
        )
        with pytest.raises(ValueError, match="ya fue pagada"):
            PaymentService.process_payment(user, order, {
                'payment_id': 'X', 'payment_method': 'Transfer', 'status': 'Completed'
            })

    def test_stock_decrements_on_payment(self, user, product):
        """Stock indicativo se descuenta correctamente en process_payment."""
        initial_stock = product.stock
        order = Order.objects.create(
            user=user, first_name='Test', last_name='User',
            phone='123', email=user.email,
            address_line_1='Test', country='AR',
            city='BA', state='1000',
            order_number='20240101004', order_total=20.0
        )
        OrderProduct.objects.create(
            order=order, user=user, product=product,
            quantity=2, purchase_price=10.0
        )

        PaymentService.process_payment(user, order, {
            'payment_id': 'PAY789',
            'payment_method': 'Transfer',
            'status': 'Completed'
        })
        product.refresh_from_db()
        assert product.stock == initial_stock - 2

    def test_process_whatsapp_atomicity_and_stock(self, user, product):
        """process_whatsapp_order descuenta stock y marca is_ordered al final."""
        from orders.services import WhatsAppService
        initial_stock = product.stock
        order = Order.objects.create(
            user=user, first_name='Test', last_name='User',
            phone='123', email=user.email,
            address_line_1='Test', country='AR',
            city='BA', state='1000',
            order_number='20240101005', order_total=20.0,
            is_ordered=False
        )
        OrderProduct.objects.create(
            order=order, user=user, product=product,
            quantity=3, purchase_price=10.0
        )

        payment, wa_link = WhatsAppService.process_whatsapp_order(order)
        order.refresh_from_db()
        product.refresh_from_db()

        assert order.is_ordered is True
        assert order.payment == payment
        assert product.stock == initial_stock - 3
        assert wa_link is not None

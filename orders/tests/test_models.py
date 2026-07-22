"""
Tests para modelos de Orders.
"""
import pytest
from orders.models import Order, Payment, OrderProduct


@pytest.mark.django_db
class TestOrderModel:
    """Tests del modelo Order."""

    def test_full_name_concatenates_names(self, user):
        """Order.full_name() retorna first_name + last_name"""
        order = Order.objects.create(
            user=user,
            first_name='Juan',
            last_name='Pérez',
            phone='123456',
            email='test@test.com',
            address_line_1='Test St',
            country='Argentina',
            city='CABA',
            state='1000',
            order_number='20240101001'
        )
        
        assert order.full_name() == 'Juan Pérez'

    def test_order_status_default_is_new(self, user):
        """Order tiene status 'New' por defecto"""
        order = Order.objects.create(
            user=user,
            first_name='Test',
            last_name='User',
            phone='123',
            email='test@test.com',
            address_line_1='Test',
            country='AR',
            city='BA',
            state='1000',
            order_number='20240101001'
        )
        
        assert order.status == 'New'

    def test_order_status_badge_and_summaries(self, user):
        """Verifica badge classes y resúmenes GEO/AEO de Order"""
        order = Order.objects.create(
            user=user,
            first_name='Test',
            last_name='User',
            phone='123',
            email='test@test.com',
            address_line_1='Test',
            country='AR',
            city='BA',
            state='1000',
            order_number='20240101001',
            status='Completed'
        )
        assert 'bg-green-100' in order.get_status_badge_class()
        assert 'Pedido #20240101001' in order.get_voice_summary()
        assert 'Bulonera Alvear' in order.get_geo_summary()

    def test_order_is_ordered_default_false(self, user):
        """Order.is_ordered es False por defecto"""
        order = Order.objects.create(
            user=user,
            first_name='Test',
            last_name='User',
            phone='123',
            email='test@test.com',
            address_line_1='Test',
            country='AR',
            city='BA',
            state='1000',
            order_number='20240101001'
        )
        
        assert order.is_ordered is False


@pytest.mark.django_db
class TestPaymentModel:
    """Tests del modelo Payment."""

    def test_payment_creation(self, user):
        """Crea un Payment correctamente"""
        payment = Payment.objects.create(
            user=user,
            payment_id='PAY123',
            payment_method='Credit Card',
            amount_id='100.00',
            status='Completed'
        )
        
        assert payment.payment_id == 'PAY123'
        assert payment.payment_method == 'Credit Card'

    def test_payment_str(self, user):
        """Payment.__str__() retorna payment_id"""
        payment = Payment.objects.create(
            user=user,
            payment_id='PAY123',
            payment_method='Credit Card',
            amount_id='100.00',
            status='Completed'
        )
        
        assert str(payment) == 'PAY123'


@pytest.mark.django_db
class TestOrderProductModel:
    """Tests del modelo OrderProduct."""

    def test_order_product_creation(self, user, product):
        """Crea un OrderProduct correctamente"""
        order = Order.objects.create(
            user=user,
            first_name='Test',
            last_name='User',
            phone='123',
            email='test@test.com',
            address_line_1='Test',
            country='AR',
            city='BA',
            state='1000',
            order_number='20240101001'
        )
        
        order_product = OrderProduct.objects.create(
            order=order,
            user=user,
            product=product,
            quantity=5,
            purchase_price=10.50
        )
        
        assert order_product.quantity == 5
        assert order_product.product == product

    def test_order_product_str(self, user, product):
        """OrderProduct.__str__() retorna product.name"""
        order = Order.objects.create(
            user=user,
            first_name='Test',
            last_name='User',
            phone='123',
            email='test@test.com',
            address_line_1='Test',
            country='AR',
            city='BA',
            state='1000',
            order_number='20240101001'
        )
        
        order_product = OrderProduct.objects.create(
            order=order,
            user=user,
            product=product,
            quantity=1,
            purchase_price=10.50
        )
        
        assert str(order_product) == product.name

"""
Tests unitarios e integrales para Modalidades de Entrega y Facturación en Checkout (Fase 4A).
"""
import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from orders.models import Order
from orders.web.forms import OrderForm
from orders.services import OrderService, WhatsAppService
from cart.models import Cart, CartItem
from store.models import Product, Category

Account = get_user_model()


@pytest.fixture
def user(db):
    return Account.objects.create_user(
        first_name='Martín',
        last_name='Fierro',
        username='mfierro',
        email='martin@alvear.com',
        password='password123'
    )


@pytest.fixture
def category(db):
    return Category.objects.create(category_name='Fijaciones', slug='fijaciones')


@pytest.fixture
def product(db, category):
    return Product.objects.create(
        name='Bulón Hexagonal G8 1/2x2',
        slug='bulon-hexagonal-g8-1-2x2',
        code='BHG8-122',
        price=Decimal('1250.00'),
        stock=100,
        is_available=True,
        category=category
    )


class TestOrderFormModalities:
    """Pruebas de validación condicional en OrderForm para entrega y facturación"""

    def test_pickup_mode_defaults_and_passes_without_address(self):
        """Retiro en mostrador no exige dirección física y autocompleta con la sede de Av. Alvear 1301"""
        data = {
            'first_name': 'Carlos',
            'last_name': 'López',
            'email': 'carlos@taller.com',
            'phone': '+54 362 4999999',
            'delivery_type': 'pickup',
            'invoice_type': 'B',
            'doc_number': '30111222',
        }
        form = OrderForm(data=data)
        assert form.is_valid(), f"Errores inesperados: {form.errors}"
        cleaned = form.cleaned_data
        assert cleaned['delivery_type'] == 'pickup'
        assert cleaned['address_line_1'] == 'Av. Alvear 1301'
        assert cleaned['city'] == 'Resistencia'
        assert cleaned['state'] == '3500'
        assert cleaned['doc_number'] == '30111222'

    def test_shipping_mode_requires_address_city_state(self):
        """Envío al interior/NEA exige dirección, ciudad y CP"""
        data = {
            'first_name': 'Carlos',
            'last_name': 'López',
            'email': 'carlos@taller.com',
            'phone': '+54 362 4999999',
            'delivery_type': 'shipping',
            'invoice_type': 'B',
        }
        form = OrderForm(data=data)
        assert not form.is_valid()
        assert 'address_line_1' in form.errors
        assert 'city' in form.errors
        assert 'state' in form.errors

    def test_shipping_mode_valid_with_full_address(self):
        """Envío al interior con dirección completa es válido"""
        data = {
            'first_name': 'Carlos',
            'last_name': 'López',
            'email': 'carlos@taller.com',
            'phone': '+54 362 4999999',
            'delivery_type': 'shipping',
            'address_line_1': 'Ruta 11 Km 1005',
            'city': 'Fontana',
            'state': '3514',
            'country': 'Argentina',
            'invoice_type': 'B',
        }
        form = OrderForm(data=data)
        assert form.is_valid(), f"Errores: {form.errors}"
        assert form.cleaned_data['delivery_type'] == 'shipping'
        assert form.cleaned_data['city'] == 'Fontana'

    def test_invoice_a_requires_cuit_and_business_name(self):
        """Factura A exige Razón Social y CUIT válido"""
        data = {
            'first_name': 'Elena',
            'last_name': 'Gómez',
            'email': 'elena@metalurgica.com',
            'phone': '+54 362 4111222',
            'delivery_type': 'pickup',
            'invoice_type': 'A',
            # Falta business_name y doc_number
        }
        form = OrderForm(data=data)
        assert not form.is_valid()
        assert 'business_name' in form.errors
        assert 'doc_number' in form.errors

    def test_invoice_a_rejects_invalid_cuit(self):
        """Factura A rechaza CUIT con dígito verificador erróneo"""
        data = {
            'first_name': 'Elena',
            'last_name': 'Gómez',
            'email': 'elena@metalurgica.com',
            'phone': '+54 362 4111222',
            'delivery_type': 'pickup',
            'invoice_type': 'A',
            'business_name': 'Metalúrgica Chaco S.R.L.',
            'doc_number': '30-11111111-9',  # CUIT inválido
        }
        form = OrderForm(data=data)
        assert not form.is_valid()
        assert 'doc_number' in form.errors

    def test_invoice_a_accepts_valid_cuit_and_formats(self):
        """Factura A acepta CUIT válido y lo formatea a XX-XXXXXXXX-X"""
        data = {
            'first_name': 'Elena',
            'last_name': 'Gómez',
            'email': 'elena@metalurgica.com',
            'phone': '+54 362 4111222',
            'delivery_type': 'pickup',
            'invoice_type': 'A',
            'business_name': 'Metalúrgica Chaco S.R.L.',
            'doc_number': '33693450239',  # CUIT AFIP válido sin guiones
        }
        form = OrderForm(data=data)
        assert form.is_valid(), f"Errores: {form.errors}"
        assert form.cleaned_data['doc_number'] == '33-69345023-9'
        assert form.cleaned_data['business_name'] == 'Metalúrgica Chaco S.R.L.'

    def test_invoice_b_rejects_malformed_dni(self):
        """Factura B con DNI de longitud incorrecta falla"""
        data = {
            'first_name': 'Carlos',
            'last_name': 'López',
            'email': 'carlos@taller.com',
            'phone': '+54 362 4999999',
            'delivery_type': 'pickup',
            'invoice_type': 'B',
            'doc_number': '12345',  # 5 dígitos
        }
        form = OrderForm(data=data)
        assert not form.is_valid()
        assert 'doc_number' in form.errors


class TestOrderServiceAndWhatsAppModalities:
    """Pruebas de persistencia y formateo de WhatsApp"""

    def test_order_creation_persists_modalities(self, user, product):
        cart = Cart.objects.create(cart_id=f'cart-mod-{user.id}')
        cart_item = CartItem.objects.create(
            cart=cart,
            user=user,
            product=product,
            quantity=5,
            is_active=True,
            purchase_price=product.price
        )
        form_data = {
            'first_name': 'Mariano',
            'last_name': 'Moreno',
            'phone': '+54 362 4001122',
            'email': user.email,
            'delivery_type': 'shipping',
            'address_line_1': 'Av. Castelli 850',
            'address_line_2': 'Galpón 3',
            'city': 'Barranqueras',
            'state': '3503',
            'country': 'Argentina',
            'invoice_type': 'A',
            'doc_number': '33-69345023-9',
            'business_name': 'Barranqueras Logística S.A.',
            'order_note': 'Dejar en portería'
        }

        order = OrderService.create_order_from_cart(
            user=user,
            form_data=form_data,
            cart_items=[cart_item],
            ip_address='192.168.1.50'
        )

        assert order.delivery_type == 'shipping'
        assert order.invoice_type == 'A'
        assert order.doc_number == '33-69345023-9'
        assert order.business_name == 'Barranqueras Logística S.A.'
        assert order.get_delivery_display_name() == 'Envío a convenir (Interior / NEA)'
        assert order.get_invoice_display_name() == 'Responsable Inscripto (Factura A)'

        # Mensaje de WhatsApp
        msg = WhatsAppService.generate_order_message(order)
        assert 'Envío a Coordinar (Interior/NEA)' in msg
        assert 'Av. Castelli 850' in msg
        assert 'Barranqueras Logística S.A.' in msg
        assert '33-69345023-9' in msg
        assert 'Dejar en portería' in msg

    def test_whatsapp_message_pickup_format(self, user, product):
        cart = Cart.objects.create(cart_id=f'cart-pickup-{user.id}')
        cart_item = CartItem.objects.create(
            cart=cart,
            user=user,
            product=product,
            quantity=1,
            is_active=True,
            purchase_price=product.price
        )
        form_data = {
            'first_name': 'Laura',
            'last_name': 'Pérez',
            'phone': '+54 362 4887766',
            'email': user.email,
            'delivery_type': 'pickup',
            'address_line_1': 'Av. Alvear 1301',
            'city': 'Resistencia',
            'state': '3500',
            'country': 'Argentina',
            'invoice_type': 'B',
            'doc_number': '28123456',
            'business_name': '',
        }

        order = OrderService.create_order_from_cart(
            user=user,
            form_data=form_data,
            cart_items=[cart_item]
        )

        msg = WhatsAppService.generate_order_message(order)
        assert 'Retiro en Mostrador (Av. Alvear 1301 - Gratis)' in msg
        assert 'Consumidor Final / Factura B (DNI: 28123456)' in msg

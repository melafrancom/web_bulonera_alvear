"""
Tests de seguridad de vistas web de Orders.
"""
import pytest
from django.urls import reverse
from orders.models import Order, OrderProduct
from account.models import Account


@pytest.mark.django_db
class TestOrderCompleteIDOR:
    """AUD-201: order_complete debe requerir login y scoping de usuario."""

    def test_anonymous_redirects_to_login(self, client):
        """Acceso anónimo a order_complete redirige a login."""
        url = reverse('orders:order_complete', args=['20240101001'])
        response = client.get(url)
        assert response.status_code == 302
        assert 'login' in response.url

    def test_user_cannot_see_other_user_order(self, client_with_user, user):
        """Usuario autenticado NO puede ver órdenes de otro usuario."""
        other_user = Account.objects.create_user(
            first_name='Other', last_name='User',
            username='other@test.com', email='other@test.com',
            password='testpass123'
        )
        order = Order.objects.create(
            user=other_user,
            first_name='Other', last_name='User',
            phone='123', email='other@test.com',
            address_line_1='Test', country='AR',
            city='BA', state='1000',
            order_number='20240101099'
        )
        url = reverse('orders:order_complete', args=[order.order_number])
        response = client_with_user.get(url)
        assert response.status_code == 404

    def test_user_can_see_own_order(self, client_with_user, user):
        """Usuario autenticado puede ver su propia orden."""
        order = Order.objects.create(
            user=user,
            first_name='Test', last_name='User',
            phone='123', email=user.email,
            address_line_1='Test', country='AR',
            city='BA', state='1000',
            order_number='20240101001'
        )
        url = reverse('orders:order_complete', args=[order.order_number])
        response = client_with_user.get(url)
        assert response.status_code == 200


@pytest.mark.django_db
class TestPaymentsView:
    """AUD-203: Vista payments solo acepta POST."""

    def test_payments_rejects_get(self, client_with_user):
        """GET a payments debe retornar 405."""
        url = reverse('orders:payments')
        response = client_with_user.get(url)
        assert response.status_code == 405

    def test_payments_unauthenticated_redirects(self, client):
        """Acceso sin login redirige."""
        url = reverse('orders:payments')
        response = client.post(url, content_type='application/json')
        assert response.status_code == 302
        assert 'login' in response.url


@pytest.mark.django_db
class TestOrderCompleteNoindex:
    """SEO: order_complete incluye noindex."""

    def test_template_has_noindex(self, client_with_user, user):
        """El template incluye meta robots noindex."""
        order = Order.objects.create(
            user=user,
            first_name='Test', last_name='User',
            phone='123', email=user.email,
            address_line_1='Test', country='AR',
            city='BA', state='1000',
            order_number='20240101001'
        )
        url = reverse('orders:order_complete', args=[order.order_number])
        response = client_with_user.get(url)
        assert response.status_code == 200
        assert b'noindex' in response.content


@pytest.mark.django_db
class TestWhatsAppRedirectTracking:
    """
    Tests de integración y renderizado web para whatsapp_redirect y tracking de conversiones.
    Cubre: T0 (json_script y unlocalize), T1 (façade frontend) y T2 (deduplicación por sesión).
    """

    def test_whatsapp_redirect_anonymous_redirects_to_login(self, client):
        # Arrange
        url = reverse('orders:whatsapp_redirect') + '?order_number=20261004001'

        # Act
        response = client.get(url)

        # Assert
        assert response.status_code == 302
        assert 'login' in response.url

    def test_whatsapp_redirect_missing_order_number_redirects_to_orders(self, client_with_user):
        # Arrange
        url = reverse('orders:whatsapp_redirect')

        # Act
        response = client_with_user.get(url)

        # Assert
        assert response.status_code == 302
        assert reverse('account:my_orders') in response.url

    def test_whatsapp_redirect_other_user_order_redirects_to_orders(self, client_with_user, user):
        # Arrange - Crear orden perteneciente a otro usuario (IDOR protection)
        other_user = Account.objects.create_user(
            first_name='Otro', last_name='Cliente',
            username='otro@test.com', email='otro@test.com',
            password='Password123'
        )
        order = Order.objects.create(
            user=other_user,
            first_name='Otro', last_name='Cliente',
            phone='123456', email='otro@test.com',
            address_line_1='Calle Falsa 123', country='AR',
            city='Resistencia', state='H3500',
            order_number='20261004999'
        )
        url = reverse('orders:whatsapp_redirect') + f'?order_number={order.order_number}'

        # Act
        response = client_with_user.get(url)

        # Assert
        assert response.status_code == 302
        assert reverse('account:my_orders') in response.url

    def test_whatsapp_redirect_renders_json_script_and_event_id_when_is_new_purchase(
        self, client_with_user, user, product
    ):
        # Arrange
        import json
        import re
        from decimal import Decimal

        order = Order.objects.create(
            user=user,
            first_name='Carlos', last_name='Gomez',
            phone='+5493624001122', email=user.email,
            address_line_1='Av. Alvear 1500', country='AR',
            city='Resistencia', state='H3500',
            order_number='20261004101',
            order_total=Decimal('3500.75')
        )
        OrderProduct.objects.create(
            order=order,
            user=user,
            product=product,
            quantity=2,
            purchase_price=Decimal('1750.37'),
            ordered=True
        )

        # Simular que venimos inmediatamente de place_order con el flag de sesión
        session = client_with_user.session
        session['ba_pending_purchase'] = order.order_number
        session.save()

        url = reverse('orders:whatsapp_redirect') + f'?order_number={order.order_number}'

        # Act
        response = client_with_user.get(url)

        # Assert
        assert response.status_code == 200
        html = response.content.decode('utf-8')

        # 1. Verificar presencia de bloques json_script (ADR-04)
        assert '<script id="ga4-purchase-data" type="application/json">' in html
        assert '<script id="meta-purchase-data" type="application/json">' in html

        # 2. Extraer y verificar que el JSON parsea limpiamente sin errores de sintaxis (ADR-04)
        ga4_match = re.search(r'<script id="ga4-purchase-data" type="application/json">([\s\S]*?)</script>', html)
        assert ga4_match is not None
        ga4_data = json.loads(ga4_match.group(1))
        assert ga4_data['transaction_id'] == '20261004101'
        assert ga4_data['value'] == 3500.75
        assert isinstance(ga4_data['value'], float)
        assert ga4_data['items'][0]['item_id'] == str(product.code)

        meta_match = re.search(r'<script id="meta-purchase-data" type="application/json">([\s\S]*?)</script>', html)
        assert meta_match is not None
        meta_data = json.loads(meta_match.group(1))
        assert meta_data['value'] == 3500.75
        assert meta_data['contents'][0]['id'] == str(product.code)

        # 3. Verificar que el event_id coincidente está embebido para la deduplicación CAPI/Pixel
        assert f"purchase.{order.order_number}" in html

    def test_whatsapp_redirect_deduplication_does_not_render_scripts_on_page_reload(
        self, client_with_user, user, product
    ):
        # Arrange
        from decimal import Decimal
        order = Order.objects.create(
            user=user,
            first_name='Carlos', last_name='Gomez',
            phone='+5493624001122', email=user.email,
            address_line_1='Av. Alvear 1500', country='AR',
            city='Resistencia', state='H3500',
            order_number='20261004102',
            order_total=Decimal('1200.00')
        )
        url = reverse('orders:whatsapp_redirect') + f'?order_number={order.order_number}'

        # Act - Petición SIN flag en sesión (simula F5 o visita posterior)
        response = client_with_user.get(url)

        # Assert
        assert response.status_code == 200
        html = response.content.decode('utf-8')

        # NO debe renderizar los scripts de compra para no duplicar eventos en Analytics/Meta
        assert 'id="ga4-purchase-data"' not in html
        assert 'id="meta-purchase-data"' not in html
        assert 'window.baTrack.meta(\'Purchase\'' not in html


@pytest.mark.django_db
class TestPlaceOrderCheckoutFlow:
    """Pruebas funcionales de place_order: redirección a /cart/ y anti-stale."""

    def test_place_order_get_empty_cart_redirects_to_cart(self, client_with_user):
        """GET a place_order sin items en el carrito debe redirigir a /cart/."""
        url = reverse('orders:place_orders')
        response = client_with_user.get(url)
        assert response.status_code == 302
        assert response.url == reverse('cart:cart')

    def test_place_order_post_service_error_redirects_to_cart(self, client_with_user, user, product, monkeypatch):
        """Si complete_checkout lanza ValueError, debe redirigir a /cart/ sin renderizar items obsoletos."""
        from cart.models import Cart, CartItem
        from orders.services import CheckoutService

        cart = Cart.objects.create(cart_id=f'cart-web-{user.id}')
        CartItem.objects.create(
            cart=cart, user=user, product=product,
            quantity=1, is_active=True, purchase_price=product.price
        )

        def mock_checkout_failure(*args, **kwargs):
            raise ValueError("Hay productos sin precio válido en tu carrito.")

        monkeypatch.setattr(CheckoutService, 'complete_checkout', mock_checkout_failure)

        url = reverse('orders:place_orders')
        post_data = {
            'first_name': 'Juan', 'last_name': 'Perez', 'phone': '+5493624112233',
            'email': user.email, 'address_line_1': 'Calle Falsa 123',
            'country': 'Argentina', 'city': 'Resistencia', 'state': 'Chaco'
        }
        response = client_with_user.post(url, post_data)
        assert response.status_code == 302
        assert response.url == reverse('cart:cart')

    def test_place_order_post_invalid_form_with_empty_cart_redirects_to_cart(self, client_with_user, user):
        """Si el formulario es inválido y el carrito se vació en paralelo, redirige a /cart/."""
        url = reverse('orders:place_orders')
        # POST con datos incompletos (sin nombre ni teléfono) y sin carrito
        response = client_with_user.post(url, {'first_name': ''})
        assert response.status_code == 302
        assert response.url == reverse('cart:cart')

    def test_place_order_post_invalid_form_with_active_cart_renders_checkout(self, client_with_user, user, product):
        """Si el formulario es inválido pero el carrito sigue activo, renderiza checkout con errores."""
        from cart.models import Cart, CartItem
        cart = Cart.objects.create(cart_id=f'cart-form-err-{user.id}')
        item = CartItem.objects.create(
            cart=cart, user=user, product=product,
            quantity=2, is_active=True, purchase_price=product.price
        )

        url = reverse('orders:place_orders')
        # Formulario deliberadamente inválido
        response = client_with_user.post(url, {'first_name': ''})
        assert response.status_code == 200
        assert 'cart/checkout.html' in [t.name for t in response.templates if t.name]
        assert 'form' in response.context
        assert response.context['form'].errors
        assert list(response.context['cart_items']) == [item]


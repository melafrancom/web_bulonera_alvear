"""
Tests de Seguridad para la App Cart (BULONERA WEB).
Cubre mitigaciones SEC-103 y SEC-108.
Sigue estrictamente el estándar de pruebas (Arrange-Act-Assert) de test-standardization.
"""
import pytest
from django.urls import reverse
from cart.models import CartItem


@pytest.mark.django_db
class TestCartSecurityRemediations:
    """Pruebas de seguridad y robustez en la app cart bajo estándar AAA."""

    def test_add_cart_open_redirect_rejected(self, client, product):
        """
        SEC-103: Prevenir Open Redirect cuando HTTP_REFERER apunta a un sitio externo malicioso.
        """
        # Arrange
        url = reverse('cart:add_cart', args=[product.id])
        data = {'quantity': 1}
        malicious_referer = 'https://evil-hacker.com/phishing-cart'

        # Act
        response = client.post(url, data, HTTP_REFERER=malicious_referer)

        # Assert
        assert response.status_code == 302
        assert response.url == reverse('store:store')
        assert 'evil-hacker.com' not in response.url

    def test_add_cart_safe_referer_accepted(self, client, product):
        """
        SEC-103: Un HTTP_REFERER local legítimo debe ser respetado.
        """
        # Arrange
        url = reverse('cart:add_cart', args=[product.id])
        data = {'quantity': 1}
        safe_referer = 'http://testserver/cart/'

        # Act
        response = client.post(url, data, HTTP_REFERER=safe_referer)

        # Assert
        assert response.status_code == 302
        assert response.url == safe_referer

    def test_add_cart_quantity_invalid_string(self, client, product):
        """
        SEC-108: Enviar una cantidad no numérica no debe arrojar error 500 (ValueError),
        sino sanitizarse a 1 de forma segura.
        """
        # Arrange
        url = reverse('cart:add_cart', args=[product.id])
        data = {'quantity': 'invalid_string_or_injection'}

        # Act
        response = client.post(url, data)

        # Assert
        assert response.status_code == 302
        cart_item = CartItem.objects.filter(product=product).first()
        assert cart_item is not None
        assert cart_item.quantity == 1

    def test_add_cart_quantity_clamped_extremes(self, client, product):
        """
        SEC-108: Cantidades negativas o exorbitantes deben limitarse al rango seguro [1, 1000].
        """
        # Arrange
        url = reverse('cart:add_cart', args=[product.id])

        # Act & Assert 1: Cantidad negativa limitada a >= 1
        client.post(url, {'quantity': -50})
        item = CartItem.objects.filter(product=product).first()
        assert item is not None
        assert item.quantity >= 1

        # Arrange 2: Limpiar carrito para aislar test de límite superior
        CartItem.objects.all().delete()

        # Act & Assert 2: Cantidad desbordada limitada a 1000
        client.post(url, {'quantity': 999999})
        item = CartItem.objects.filter(product=product).first()
        assert item is not None
        assert item.quantity == 1000


@pytest.mark.django_db
class TestCartMethodSecurity:
    """
    AUD-CART-001: Verificación estricta de que las mutaciones de estado
    requieren método POST y rechazan GET con HTTP 405 Method Not Allowed.
    """

    def test_add_cart_get_method_rejected_405(self, client, product):
        """GET a add_cart debe retornar 405 Method Not Allowed."""
        url = reverse('cart:add_cart', args=[product.id])
        response = client.get(url)
        assert response.status_code == 405

    def test_remove_cart_get_method_rejected_405(self, client, product):
        """GET a remove_cart debe retornar 405 Method Not Allowed."""
        url = reverse('cart:remove_cart', args=[product.id, 9999])
        response = client.get(url)
        assert response.status_code == 405

    def test_remove_cart_item_get_method_rejected_405(self, client, product):
        """GET a remove_cart_item debe retornar 405 Method Not Allowed."""
        url = reverse('cart:remove_cart_item', args=[product.id, 9999])
        response = client.get(url)
        assert response.status_code == 405

    def test_add_cart_post_succeeds(self, client, product):
        """POST a add_cart agrega el producto y redirige exitosamente."""
        url = reverse('cart:add_cart', args=[product.id])
        response = client.post(url, {'quantity': 2})
        assert response.status_code == 302
        item = CartItem.objects.filter(product=product).first()
        assert item is not None
        assert item.quantity == 2

    def test_remove_cart_post_decrements_item(self, client, product):
        """POST a remove_cart decrementa la cantidad del ítem."""
        url_add = reverse('cart:add_cart', args=[product.id])
        client.post(url_add, {'quantity': 3})
        item = CartItem.objects.filter(product=product).first()
        assert item.quantity == 3

        url_remove = reverse('cart:remove_cart', args=[product.id, item.id])
        response = client.post(url_remove)
        assert response.status_code == 302
        item.refresh_from_db()
        assert item.quantity == 2

    def test_remove_cart_item_post_deletes_completely(self, client, product):
        """POST a remove_cart_item elimina completamente el ítem del carrito."""
        url_add = reverse('cart:add_cart', args=[product.id])
        client.post(url_add, {'quantity': 3})
        item = CartItem.objects.filter(product=product).first()
        assert item is not None

        url_delete = reverse('cart:remove_cart_item', args=[product.id, item.id])
        response = client.post(url_delete)
        assert response.status_code == 302
        assert not CartItem.objects.filter(id=item.id).exists()


@pytest.mark.django_db
class TestCartClampingAndServiceSecurity:
    """
    AUD-CART-002: Verificación de clamp_quantity centralizado en CartService.
    """

    def test_clamp_quantity_bounds(self):
        from cart.services import CartService
        # Normal
        assert CartService.clamp_quantity(5) == 5
        # Límite inferior
        assert CartService.clamp_quantity(0) == 1
        assert CartService.clamp_quantity(-100) == 1
        # Límite superior
        assert CartService.clamp_quantity(1000) == 1000
        assert CartService.clamp_quantity(1001) == 1000
        assert CartService.clamp_quantity(999999) == 1000
        # Inválido
        assert CartService.clamp_quantity('not_a_number') == 1
        assert CartService.clamp_quantity(None) == 1

    def test_update_quantity_service_bounds(self, product):
        from cart.services import CartService
        from cart.models import Cart
        cart = Cart.objects.create(cart_id='test-session-clamping')
        item = CartItem.objects.create(cart=cart, product=product, quantity=1)

        # Actualizar a valor normal
        updated = CartService.update_quantity(item.id, 10, cart_id='test-session-clamping')
        assert updated.quantity == 10

        # Actualizar a valor por encima de 1000
        updated = CartService.update_quantity(item.id, 5000, cart_id='test-session-clamping')
        assert updated.quantity == 1000

        # Actualizar a valor menor a 1
        updated = CartService.update_quantity(item.id, -20, cart_id='test-session-clamping')
        assert updated.quantity == 1


@pytest.mark.django_db
class TestCartAPISecurityBounds:
    """
    AUD-CART-SER-001: Verificación de validación de límites en API Serializers.
    """

    def test_api_add_item_rejects_exorbitant_quantity(self, authenticated_api_client, product):
        """API rechaza agregar más de 1000 unidades con 400 Bad Request."""
        url = reverse('cart_api:cart-add')
        response = authenticated_api_client.post(url, {'product_id': product.id, 'quantity': 1001}, format='json')
        assert response.status_code == 400
        assert 'quantity' in response.data or 'error' in response.data or 'message' in response.data

    def test_api_add_item_rejects_zero_or_negative_quantity(self, authenticated_api_client, product):
        """API rechaza cantidad <= 0 con 400 Bad Request."""
        url = reverse('cart_api:cart-add')
        response = authenticated_api_client.post(url, {'product_id': product.id, 'quantity': 0}, format='json')
        assert response.status_code == 400


@pytest.mark.django_db
class TestCartItemFinancialPrecision:
    """
    AUD-CART-NEW-002: Verificación de precisión Decimal en CartItem.
    """

    def test_purchase_price_stores_exact_decimal(self, product):
        from decimal import Decimal
        product.price = 1499.99
        product.save()

        item = CartItem.objects.create(
            product=product,
            quantity=3
        )
        assert isinstance(item.purchase_price, Decimal)
        assert item.purchase_price == Decimal('1499.99')
        assert isinstance(item.sub_total, Decimal)
        assert item.sub_total == Decimal('4499.97')

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

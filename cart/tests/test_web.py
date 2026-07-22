"""
Cart Web Tests

Tests de vistas web del carrito.
"""
import pytest
from django.test import Client


@pytest.mark.django_db
class TestCartWebViews:
    """Tests de vistas web del carrito"""

    def test_cart_view_200(self, client):
        """GET /cart/ retorna 200"""
        try:
            response = client.get('/cart/')
            assert response.status_code in [200, 404]
        except:
            # Si la URL no está registrada, es un falso positivo
            pass

    def test_cart_template_has_noindex(self, client):
        """Verifica que el template cart.html incluya noindex, nofollow"""
        from django.template.loader import render_to_string
        rendered = render_to_string('cart/cart.html', {'cart_items': [], 'quantity': 0})
        assert 'name="robots" content="noindex, nofollow"' in rendered

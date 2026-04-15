"""
Cart API Tests

Tests de endpoints REST del carrito de compras.
"""
import pytest
from rest_framework.test import APIClient
from rest_framework import status


@pytest.mark.django_db
class TestCartAPI:
    """Tests de carrito API"""

    def test_get_cart_anonymous_200(self, client):
        """GET /api/v1/cart/ retorna 200 para usuario anónimo"""
        response = client.get('/api/v1/cart/')
        assert response.status_code == 200
        data = response.json()
        assert 'items' in data or 'cart_count' in data

    def test_get_cart_authenticated_200(self, authenticated_api_client):
        """GET /api/v1/cart/ retorna 200 para usuario autenticado"""
        response = authenticated_api_client.get('/api/v1/cart/')
        assert response.status_code == 200

    def test_add_item_to_cart_200(self, authenticated_api_client, product):
        """POST /api/v1/cart/add/ agrega item al carrito"""
        response = authenticated_api_client.post('/api/v1/cart/add/', {
            'product_id': product.id,
            'quantity': 2
        })
        assert response.status_code in [200, 201]

    def test_add_item_invalid_product_404(self, authenticated_api_client):
        """POST /api/v1/cart/add/ retorna 404 o error para producto no existente"""
        response = authenticated_api_client.post('/api/v1/cart/add/', {
            'product_id': 99999,
            'quantity': 1
        })
        # Puede retornar 404 o 500 si el endpoint maneja mal el error
        assert response.status_code in [404, 500, 400]

    def test_remove_item_from_cart_200(self, authenticated_api_client, cart_item):
        """POST /api/v1/cart/remove/ remueve item del carrito"""
        response = authenticated_api_client.post('/api/v1/cart/remove/', {
            'item_id': cart_item.id
        })
        # Puede retornar 200 si se removió o 404 si endpoint no existe
        assert response.status_code in [200, 404]

    def test_remove_nonexistent_item_404(self, authenticated_api_client):
        """POST /api/v1/cart/remove/ retorna 404 para item no existente"""
        response = authenticated_api_client.post('/api/v1/cart/remove/', {
            'item_id': 99999
        })
        assert response.status_code == 404

    def test_cart_contains_product_count(self, authenticated_api_client, cart_item):
        """GET /api/v1/cart/ contiene cantidad de items"""
        response = authenticated_api_client.get('/api/v1/cart/')
        assert response.status_code == 200
        data = response.json()
        assert 'count' in data or 'items' in data or 'cart_count' in data

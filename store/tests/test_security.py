"""
Tests de Seguridad para la App Store (BULONERA WEB).
Cubre mitigaciones SEC-101, SEC-102, SEC-104, SEC-105, SEC-106, SEC-107, SEC-109.
Sigue estrictamente el estándar de pruebas (Arrange-Act-Assert) de test-standardization.
"""
import pytest
from unittest.mock import patch
from django.urls import reverse
from store.models import ReviewRating, Product
from orders.models import Order, OrderProduct
from store.api.serializers import ProductListSerializer, ProductDetailSerializer


@pytest.mark.django_db
class TestStoreSecurityRemediations:
    """Pruebas de seguridad y robustez en la app store bajo estándar AAA."""

    def test_submit_review_bola_unpurchased_product(self, client_with_user, user, product):
        """
        SEC-101: Un usuario autenticado no debe poder reseñar un producto
        que no ha comprado previamente (prevención BOLA/IDOR).
        """
        # Arrange
        url = reverse('store:submit_review', args=[product.id])
        data = {
            'subject': 'Excelente producto',
            'review': 'Muy buena calidad del tornillo',
            'rating': 5,
        }

        # Act
        response = client_with_user.post(url, data)

        # Assert
        assert response.status_code == 302
        assert not ReviewRating.objects.filter(user=user, product=product).exists()

    def test_submit_review_authorized_purchased_product(self, client_with_user, user, product):
        """
        SEC-101: Un usuario que sí compró el producto puede publicar su reseña.
        """
        # Arrange
        order = Order.objects.create(
            user=user,
            order_number='TEST-ORD-001',
            first_name=user.first_name,
            last_name=user.last_name,
            phone='12345678',
            email=user.email,
            address_line_1='Av. Siempre Viva 123',
            order_total=100.0,
            ip='127.0.0.1',
            status='Completed',
            is_ordered=True
        )
        OrderProduct.objects.create(
            order=order,
            user=user,
            product=product,
            quantity=2,
            purchase_price=product.price,
            ordered=True
        )
        url = reverse('store:submit_review', args=[product.id])
        data = {
            'subject': 'Excelente compra',
            'review': 'Compré y probé, excelente calidad',
            'rating': 4.5,
        }

        # Act
        response = client_with_user.post(url, data)

        # Assert
        assert response.status_code == 302
        review = ReviewRating.objects.filter(user=user, product=product).first()
        assert review is not None
        assert review.rating == 4.5
        assert review.subject == 'Excelente compra'

    def test_submit_review_open_redirect_rejected(self, client_with_user, user, product):
        """
        SEC-102: Prevenir Open Redirect cuando HTTP_REFERER apunta a un dominio externo malicioso.
        """
        # Arrange
        url = reverse('store:submit_review', args=[product.id])
        data = {
            'subject': 'Test',
            'review': 'Test review',
            'rating': 3,
        }
        malicious_referer = 'https://evil-attacker.com/malicious/phishing'

        # Act
        response = client_with_user.post(url, data, HTTP_REFERER=malicious_referer)

        # Assert
        assert response.status_code == 302
        assert response.url == reverse('store:store')
        assert 'evil-attacker.com' not in response.url

    def test_submit_review_safe_referer_accepted(self, client_with_user, user, product):
        """
        SEC-102: Un HTTP_REFERER local legítimo debe ser respetado.
        """
        # Arrange
        url = reverse('store:submit_review', args=[product.id])
        safe_referer = 'http://testserver/store/'
        data = {'subject': 'Test', 'review': 'Test', 'rating': 5}

        # Act
        response = client_with_user.post(url, data, HTTP_REFERER=safe_referer)

        # Assert
        assert response.status_code == 302
        assert response.url == safe_referer

    def test_google_merchant_feed_error_info_leak_sanitized(self, client):
        """
        SEC-104: La vista pública de feed de Google Merchant no debe filtrar
        detalles de excepciones internas (stack traces, variables de entorno o paths).
        """
        # Arrange & Act
        with patch('store.services.FeedService.get_google_merchant_feed_data', side_effect=RuntimeError("Secret DB Connection string")):
            response = client.get(reverse('store:google_merchant_feed'))

            # Assert
            assert response.status_code == 500
            content = response.content.decode('utf-8')
            assert 'Secret DB Connection' not in content
            assert 'Error interno al generar el feed' in content

    def test_api_google_merchant_feed_error_info_leak_sanitized(self, api_client):
        """
        SEC-105: El endpoint API de feed de Google Merchant tampoco debe filtrar
        detalles de excepciones internas.
        """
        # Arrange & Act
        with patch('store.services.FeedService.get_google_merchant_feed_data', side_effect=RuntimeError("Sensitive backend failure info")):
            response = api_client.get('/api/v1/store/feeds/google_merchant_xml/')

            # Assert
            assert response.status_code == 500
            content = response.content.decode('utf-8')
            assert 'Sensitive backend failure info' not in content
            assert 'Error interno al generar el feed' in content

    def test_search_keyword_length_limit(self, client):
        """
        SEC-109: La búsqueda de productos con keywords extremadamente largas
        debe sanitizarse y truncarse a 100 caracteres sin causar DoS.
        """
        # Arrange
        long_keyword = 'A' * 1000

        # Act
        response = client.get(reverse('store:search'), {'q': long_keyword})

        # Assert
        assert response.status_code == 200

    def test_api_search_viewset_pagination(self, api_client, product):
        """
        SEC-106: El endpoint de búsqueda API debe contar con paginación
        (page, count, total_pages, results).
        """
        # Arrange
        search_url = f'/api/v1/store/search/?keyword={product.name[:5]}'

        # Act
        response = api_client.get(search_url)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert 'count' in data
        assert 'page' in data
        assert 'total_pages' in data
        assert 'results' in data
        assert isinstance(data['results'], list)

    def test_product_serializers_use_annotated_review(self, product):
        """
        SEC-107: ProductListSerializer y ProductDetailSerializer deben utilizar
        valores pre-anotados si están disponibles, evitando queries N+1.
        """
        # Arrange
        product.annotated_avg_review = 4.5
        product.annotated_review_count = 12

        # Act
        list_serializer = ProductListSerializer(product)
        detail_serializer = ProductDetailSerializer(product)

        # Assert
        assert list_serializer.data['average_review'] == 4.5
        assert list_serializer.data['review_count'] == 12
        assert detail_serializer.data['average_review'] == 4.5
        assert detail_serializer.data['review_count'] == 12

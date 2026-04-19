"""
Store API Tests

Tests de endpoints REST para productos, búsqueda, reviews, FAQs y carrusel.
"""
import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse

from store.models import Product, ReviewRating, CarouselImage, FAQ, FAQCategory
from store.services import ReviewService


@pytest.mark.django_db
class TestProductAPI:
    """Tests de la API de productos"""

    def test_list_products_200(self, client, category, product):
        """GET /api/v1/store/products/ retorna 200"""
        response = client.get('/api/v1/store/products/')
        assert response.status_code == 200
        assert 'results' in response.json()

    def test_list_products_empty(self, client):
        """GET /api/v1/store/products/ con BD vacía retorna lista vacía"""
        response = client.get('/api/v1/store/products/')
        assert response.status_code == 200
        data = response.json()
        assert data['count'] == 0

    def test_retrieve_product_by_slug_200(self, client, product):
        """GET /api/v1/store/products/{slug}/ retorna 200"""
        response = client.get(f'/api/v1/store/products/{product.slug}/')
        assert response.status_code == 200
        data = response.json()
        assert data['name'] == product.name

    def test_retrieve_product_not_found_404(self, client):
        """GET /api/v1/store/products/slug-inexistente/ retorna 404"""
        response = client.get('/api/v1/store/products/slug-inexistente/')
        assert response.status_code == 404

    def test_products_by_category(self, client, category, product):
        """GET /api/v1/store/products/by_category/?slug={slug} retorna productos de categoría"""
        response = client.get(f'/api/v1/store/products/by_category/?slug={category.slug}')
        assert response.status_code == 200

    def test_products_on_sale(self, client, category):
        """GET /api/v1/store/products/on_sale/ retorna productos en oferta"""
        Product.objects.create(
            code='SALE1',
            name='Producto en Oferta',
            slug='producto-en-oferta',
            price=100.0,
            sale_price=50.0,
            stock=10,
            category=category,
            is_on_sale=True
        )
        response = client.get('/api/v1/store/products/on_sale/')
        assert response.status_code == 200

    def test_product_reviews_endpoint(self, client, product, user):
        """GET /api/v1/store/products/{slug}/reviews/ retorna reviews"""
        ReviewService.create_review(
            user_id=user.id,
            product_id=product.id,
            subject='Excelente',
            review='Muy bueno',
            rating=5.0,
            ip='127.0.0.1'
        )
        response = client.get(f'/api/v1/store/products/{product.slug}/reviews/')
        assert response.status_code == 200

    def test_product_faqs_endpoint(self, client, product):
        """GET /api/v1/store/products/{slug}/faqs/ retorna FAQs"""
        response = client.get(f'/api/v1/store/products/{product.slug}/faqs/')
        assert response.status_code == 200


@pytest.mark.django_db
class TestSearchAPI:
    """Tests de búsqueda de API"""

    def test_search_with_keyword_200(self, client, category):
        """GET /api/v1/store/search/?keyword=tornillo retorna 200 con resultados"""
        Product.objects.create(
            code='TORNILLO',
            name='Tornillo de Acero',
            slug='tornillo-acero',
            price=10.0,
            stock=100,
            category=category,
            is_available=True
        )
        response = client.get('/api/v1/store/search/?keyword=tornillo')
        assert response.status_code == 200
        data = response.json()
        assert 'results' in data
        assert data['keyword'] == 'tornillo'

    def test_search_without_keyword_returns_available(self, client, product):
        """GET /api/v1/store/search/ sin keyword retorna todos los disponibles"""
        response = client.get('/api/v1/store/search/')
        assert response.status_code == 200
        data = response.json()
        assert data['count'] > 0

    def test_search_no_results(self, client):
        """GET /api/v1/store/search/?keyword=inexistente retorna 0 resultados"""
        response = client.get('/api/v1/store/search/?keyword=xyzinexistente')
        assert response.status_code == 200
        data = response.json()
        assert data['count'] == 0


@pytest.mark.django_db
class TestReviewAPI:
    """Tests de reviews de API"""

    def test_create_review_unauthorized_401(self, api_client, product):
        """POST /api/v1/store/reviews/ sin login retorna 401"""
        response = api_client.post('/api/v1/store/reviews/', {
            'product_id': product.id,
            'subject': 'Test',
            'review': 'Test review',
            'rating': 5.0
        })
        assert response.status_code in [401, 403]  # Puede ser 401 (DRF) o 403 (CSRF)

    def test_create_review_authenticated_200(self, client, authenticated_api_client, product, user):
        """POST /api/v1/store/reviews/ autenticado crea review"""
        # Simular que el usuario compró el producto
        from orders.models import Order, OrderProduct
        order = Order.objects.create(
            user=user,
            first_name='Test',
            last_name='User',
            phone='123456',
            email=user.email,
            address_line_1='Test St',
            country='Argentina',
            city='CABA',
            state='1000',
            is_ordered=True
        )
        OrderProduct.objects.create(
            order=order,
            user=user,
            product=product,
            quantity=1,
            purchase_price=10.0
        )

        response = authenticated_api_client.post('/api/v1/store/reviews/', {
            'product_id': product.id,
            'subject': 'Excelente producto',
            'review': 'Muy satisfecho con la compra',
            'rating': 5.0
        })
        assert response.status_code in [200, 201]


@pytest.mark.django_db
class TestFAQAPI:
    """Tests de FAQs de API"""

    def test_list_faqs_200(self, client):
        """GET /api/v1/store/faqs/ retorna 200"""
        FAQCategory.objects.create(name='General', order=1)
        response = client.get('/api/v1/store/faqs/')
        assert response.status_code == 200

    def test_faqs_return_list(self, client):
        """GET /api/v1/store/faqs/ retorna lista"""
        category = FAQCategory.objects.create(name='Help', order=1)
        FAQ.objects.create(
            category=category,
            question='¿Cómo compro?',
            answer='Haz clic en comprar',
            order=1,
            is_active=True
        )
        response = client.get('/api/v1/store/faqs/')
        assert response.status_code == 200


@pytest.mark.django_db
class TestCarouselAPI:
    """Tests de carrusel de API"""

    def test_carousel_list_200(self, client):
        """GET /api/v1/store/carousel/ retorna 200"""
        response = client.get('/api/v1/store/carousel/')
        assert response.status_code == 200

    def test_carousel_active_images(self, client):
        """GET /api/v1/store/carousel/ retorna solo imágenes activas"""
        CarouselImage.objects.create(title='Slide 1', position=1, is_active=True)
        CarouselImage.objects.create(title='Slide 2', position=2, is_active=False)
        
        response = client.get('/api/v1/store/carousel/')
        assert response.status_code == 200
        data = response.json()
        assert data['count'] == 1
        assert len(data['results']) == 1

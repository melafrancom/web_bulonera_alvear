"""
Tests para Fase 2 - API DRF Completa
"""
import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from account.models import Account
from store.models import Product
from category.models import Category


@pytest.mark.django_db
class TestAPIPhase2:
    """Tests para validar la Fase 2 de la API"""
    
    def setup_method(self):
        """Setup para cada test"""
        self.client = APIClient()
        
        # Crear usuario de prueba ACTIVO
        self.user = Account.objects.create_user(
            email='test@example.com',
            username='testuser',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.user.is_active = True
        self.user.save()
        
        # Crear categoría y producto de prueba
        self.category = Category.objects.create(
            category_name='Test Category',
            slug='test-category'
        )
        
        self.product = Product.objects.create(
            code='TEST001',
            name='Test Product',
            slug='test-product',
            price=100.00,
            stock=10,
            category=self.category
        )
    
    def test_api_products_list(self):
        """Test GET /api/v1/store/products/"""
        response = self.client.get('/api/v1/store/products/')
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data or isinstance(response.data, list)
    
    def test_api_product_detail(self):
        """Test GET /api/v1/store/products/{slug}/"""
        response = self.client.get(f'/api/v1/store/products/{self.product.slug}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['slug'] == self.product.slug
    
    def test_api_categories_list(self):
        """Test GET /api/v1/category/categories/"""
        response = self.client.get('/api/v1/category/categories/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_api_search(self):
        """Test GET /api/v1/store/search/?keyword=test"""
        response = self.client.get('/api/v1/store/search/?keyword=test')
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
    
    def test_api_cart_list_anonymous(self):
        """Test GET /api/v1/cart/ (usuario anónimo)"""
        response = self.client.get('/api/v1/cart/')
        assert response.status_code == status.HTTP_200_OK
        assert 'items' in response.data or 'cart_count' in response.data
    
    def test_api_login_returns_token(self):
        """Test POST /api/v1/account/auth/login/ devuelve token"""
        response = self.client.post('/api/v1/account/auth/login/', {
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        assert response.status_code == status.HTTP_200_OK
        assert 'token' in response.data
        assert 'user' in response.data
        assert response.data['user']['email'] == 'test@example.com'
    
    def test_api_authenticated_request_with_token(self):
        """Test request autenticado con token"""
        # Login para obtener token
        login_response = self.client.post('/api/v1/account/auth/login/', {
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        token = login_response.data['token']
        
        # Request con token
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        response = self.client.get('/api/v1/account/profile/me/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['email'] == 'test@example.com'
    
    def test_api_logout_deletes_token(self):
        """Test POST /api/v1/account/auth/logout/ elimina token"""
        # Login
        login_response = self.client.post('/api/v1/account/auth/login/', {
            'email': 'test@example.com',
            'password': 'testpass123'
        })
        token = login_response.data['token']
        
        # Logout
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        response = self.client.post('/api/v1/account/auth/logout/')
        assert response.status_code == status.HTTP_200_OK
        
        # Verificar que el token ya no funciona (puede ser 401 o 403)
        response = self.client.get('/api/v1/account/profile/me/')
        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]
    
    def test_api_carousel(self):
        """Test GET /api/v1/store/carousel/"""
        response = self.client.get('/api/v1/store/carousel/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_api_faqs(self):
        """Test GET /api/v1/store/faqs/"""
        response = self.client.get('/api/v1/store/faqs/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_api_schema_available(self):
        """Test GET /api/schema/ (OpenAPI schema)"""
        response = self.client.get('/api/schema/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_api_docs_available(self):
        """Test GET /api/docs/ (Swagger UI)"""
        response = self.client.get('/api/docs/')
        assert response.status_code == status.HTTP_200_OK

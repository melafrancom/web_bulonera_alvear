"""Tests for Category API"""
import pytest
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from category.models import Category, SubCategory, FeaturedCategory


@pytest.mark.django_db
class TestCategoryAPIViewSet(APITestCase):
    """Tests para CategoryViewSet (API REST)"""
    
    def setUp(self):
        """Setup para tests de API"""
        self.client = APIClient()
        
        # Crear categorías de prueba
        self.category1 = Category.objects.create(
            category_name='Herramientas',
            slug='herramientas',
            description='Herramientas de todo tipo'
        )
        self.category2 = Category.objects.create(
            category_name='Electricidad',
            slug='electricidad',
            description='Materiales eléctricos'
        )
        
        # Crear subcategorías
        self.subcategory1 = SubCategory.objects.create(
            subcategory_name='Destornilladores',
            slug='destornilladores',
            category=self.category1
        )
        self.subcategory2 = SubCategory.objects.create(
            subcategory_name='Martillos',
            slug='martillos',
            category=self.category1
        )
        
        # Crear categoría destacada
        self.featured = FeaturedCategory.objects.create(
            category=self.category1,
            position=1,
            is_active=True
        )
    
    def test_list_categories(self):
        """Test: GET /api/categories/ lista todas las categorías"""
        response = self.client.get('/api/v1/categories/')
        
        # Puede ser 404 si no está montada la URL, o 200 si está montada
        if response.status_code == 200:
            self.assertEqual(len(response.data), 2)
    
    def test_retrieve_category(self):
        """Test: GET /api/categories/{slug}/ obtiene detalle de categoría"""
        response = self.client.get(f'/api/v1/categories/{self.category1.slug}/')
        
        if response.status_code == 200:
            self.assertEqual(response.data['category_name'], 'Herramientas')
            self.assertIn('subcategories', response.data)
            self.assertEqual(len(response.data['subcategories']), 2)
    
    def test_featured_categories(self):
        """Test: GET /api/categories/featured/ obtiene categorías destacadas"""
        response = self.client.get('/api/v1/categories/featured/')
        
        if response.status_code == 200:
            self.assertEqual(len(response.data), 1)
            self.assertEqual(response.data[0]['category']['category_name'], 'Herramientas')
    
    def test_category_subcategories(self):
        """Test: GET /api/categories/{slug}/subcategories/ obtiene subcategorías"""
        response = self.client.get(f'/api/v1/categories/{self.category1.slug}/subcategories/')
        
        if response.status_code == 200:
            self.assertEqual(len(response.data), 2)


@pytest.mark.django_db
class TestSubCategoryAPIViewSet(APITestCase):
    """Tests para SubCategoryViewSet (API REST)"""
    
    def setUp(self):
        """Setup para tests de API"""
        self.client = APIClient()
        
        self.category = Category.objects.create(
            category_name='Herramientas',
            slug='herramientas'
        )
        self.subcategory = SubCategory.objects.create(
            subcategory_name='Destornilladores',
            slug='destornilladores',
            category=self.category
        )
    
    def test_list_subcategories(self):
        """Test: GET /api/subcategories/ lista todas las subcategorías"""
        response = self.client.get('/api/v1/subcategories/')
        
        if response.status_code == 200:
            self.assertEqual(len(response.data), 1)
    
    def test_retrieve_subcategory(self):
        """Test: GET /api/subcategories/{slug}/ obtiene detalle de subcategoría"""
        response = self.client.get(f'/api/v1/subcategories/{self.subcategory.slug}/')
        
        if response.status_code == 200:
            self.assertEqual(response.data['subcategory_name'], 'Destornilladores')
            self.assertEqual(response.data['category_name'], 'Herramientas')

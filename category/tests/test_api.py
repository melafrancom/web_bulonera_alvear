"""Tests for Category API"""
import pytest
from django.urls import reverse
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
        """Test: GET /api/v1/category/categories/ lista todas las categorías"""
        # Arrange
        url = reverse('category_api:category-list')
        
        # Act
        response = self.client.get(url)
        
        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data) if isinstance(response.data, dict) else response.data
        count = response.data.get('count', len(results)) if isinstance(response.data, dict) else len(results)
        self.assertEqual(count, 2)
        self.assertEqual(len(results), 2)
    
    def test_retrieve_category(self):
        """Test: GET /api/v1/category/categories/{slug}/ obtiene detalle de categoría"""
        # Arrange
        url = reverse('category_api:category-detail', kwargs={'slug': self.category1.slug})
        
        # Act
        response = self.client.get(url)
        
        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['category_name'], 'Herramientas')
        self.assertIn('subcategories', response.data)
        self.assertEqual(len(response.data['subcategories']), 2)
    
    def test_featured_categories(self):
        """Test: GET /api/v1/category/categories/featured/ obtiene categorías destacadas"""
        # Arrange
        url = reverse('category_api:category-featured')
        
        # Act
        response = self.client.get(url)
        
        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['category']['category_name'], 'Herramientas')
    
    def test_category_subcategories(self):
        """Test: GET /api/v1/category/categories/{slug}/subcategories/ obtiene subcategorías"""
        # Arrange
        url = reverse('category_api:category-subcategories', kwargs={'slug': self.category1.slug})
        
        # Act
        response = self.client.get(url)
        
        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
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
        """Test: GET /api/v1/category/subcategories/ lista todas las subcategorías"""
        # Arrange
        url = reverse('category_api:subcategory-list')
        
        # Act
        response = self.client.get(url)
        
        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data) if isinstance(response.data, dict) else response.data
        count = response.data.get('count', len(results)) if isinstance(response.data, dict) else len(results)
        self.assertEqual(count, 1)
        self.assertEqual(len(results), 1)
    
    def test_retrieve_subcategory(self):
        """Test: GET /api/v1/category/subcategories/{slug}/ obtiene detalle de subcategoría"""
        # Arrange
        url = reverse('category_api:subcategory-detail', kwargs={'slug': self.subcategory.slug})
        
        # Act
        response = self.client.get(url)
        
        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['subcategory_name'], 'Destornilladores')
        self.assertEqual(response.data['category_name'], 'Herramientas')

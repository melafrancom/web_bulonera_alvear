"""Tests for Category Models"""
import pytest
from django.test import TestCase
from category.models import Category, SubCategory, FeaturedCategory


@pytest.mark.django_db
class TestCategoryModel(TestCase):
    """Tests para el modelo Category"""
    
    def setUp(self):
        """Setup para tests de Category"""
        self.category = Category.objects.create(
            category_name='Herramientas',
            slug='herramientas',
            description='Herramientas de todo tipo'
        )
    
    def test_category_creation(self):
        """Test: Crear categoría exitosamente"""
        self.assertEqual(self.category.category_name, 'Herramientas')
        self.assertEqual(self.category.slug, 'herramientas')
        self.assertTrue(Category.objects.filter(slug='herramientas').exists())
    
    def test_category_str_representation(self):
        """Test: Representación string de categoría"""
        self.assertEqual(str(self.category), 'Herramientas')
    
    def test_category_get_url(self):
        """Test: Método get_url de categoría"""
        url = self.category.get_url()
        self.assertIn('herramientas', url)
    
    def test_category_unique_slug(self):
        """Test: Slug de categoría debe ser único"""
        with self.assertRaises(Exception):
            Category.objects.create(
                category_name='Herramientas 2',
                slug='herramientas'  # Slug duplicado
            )


@pytest.mark.django_db
class TestSubCategoryModel(TestCase):
    """Tests para el modelo SubCategory"""
    
    def setUp(self):
        """Setup para tests de SubCategory"""
        self.category = Category.objects.create(
            category_name='Herramientas',
            slug='herramientas'
        )
        self.subcategory = SubCategory.objects.create(
            subcategory_name='Destornilladores',
            slug='destornilladores',
            category=self.category
        )
    
    def test_subcategory_creation(self):
        """Test: Crear subcategoría exitosamente"""
        self.assertEqual(self.subcategory.subcategory_name, 'Destornilladores')
        self.assertEqual(self.subcategory.category, self.category)
    
    def test_subcategory_str_representation(self):
        """Test: Representación string de subcategoría"""
        self.assertEqual(str(self.subcategory), 'Destornilladores')
    
    def test_subcategory_get_url(self):
        """Test: Método get_url de subcategoría"""
        url = self.subcategory.get_url()
        self.assertIn('herramientas', url)
        self.assertIn('destornilladores', url)
    
    def test_subcategory_related_name(self):
        """Test: Related name 'subcategories' funciona"""
        subcategories = self.category.subcategories.all()
        self.assertEqual(subcategories.count(), 1)
        self.assertEqual(subcategories.first(), self.subcategory)


@pytest.mark.django_db
class TestFeaturedCategoryModel(TestCase):
    """Tests para el modelo FeaturedCategory"""
    
    def setUp(self):
        """Setup para tests de FeaturedCategory"""
        self.category = Category.objects.create(
            category_name='Herramientas',
            slug='herramientas'
        )
        self.featured = FeaturedCategory.objects.create(
            category=self.category,
            position=1,
            is_active=True
        )
    
    def test_featured_category_creation(self):
        """Test: Crear categoría destacada exitosamente"""
        self.assertEqual(self.featured.category, self.category)
        self.assertEqual(self.featured.position, 1)
        self.assertTrue(self.featured.is_active)
    
    def test_featured_category_str_representation(self):
        """Test: Representación string de categoría destacada"""
        self.assertEqual(str(self.featured), 'Herramientas')
    
    def test_featured_category_ordering(self):
        """Test: Ordenamiento por posición"""
        featured2 = FeaturedCategory.objects.create(
            category=Category.objects.create(
                category_name='Electricidad',
                slug='electricidad'
            ),
            position=0,
            is_active=True
        )
        
        featured_list = list(FeaturedCategory.objects.all())
        self.assertEqual(featured_list[0], featured2)  # position=0 primero
        self.assertEqual(featured_list[1], self.featured)  # position=1 segundo

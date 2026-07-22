"""Tests for Category Services"""
import pytest
from django.test import TestCase
from category.models import Category, SubCategory, FeaturedCategory
from category.services import CategoryService, SubCategoryService


@pytest.mark.django_db
class TestCategoryService(TestCase):
    """Tests para CategoryService"""
    
    def setUp(self):
        """Setup para tests del servicio"""
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
        
        self.featured = FeaturedCategory.objects.create(
            category=self.category1,
            position=1,
            is_active=True
        )
    
    def test_get_all_categories(self):
        """Test: Obtener todas las categorías"""
        categories = CategoryService.get_all_categories()
        self.assertEqual(categories.count(), 2)
    
    def test_get_category_by_slug_exists(self):
        """Test: Obtener categoría por slug existente"""
        category = CategoryService.get_category_by_slug('herramientas')
        self.assertIsNotNone(category)
        self.assertEqual(category.category_name, 'Herramientas')
    
    def test_get_category_by_slug_not_exists(self):
        """Test: Obtener categoría por slug inexistente"""
        category = CategoryService.get_category_by_slug('no-existe')
        self.assertIsNone(category)
    
    def test_get_featured_categories(self):
        """Test: Obtener categorías destacadas activas"""
        featured = CategoryService.get_featured_categories()
        self.assertEqual(featured.count(), 1)
        self.assertEqual(featured.first().category, self.category1)
    
    def test_get_featured_categories_only_active(self):
        """Test: Solo obtener categorías destacadas activas"""
        # Crear una destacada inactiva
        FeaturedCategory.objects.create(
            category=self.category2,
            position=0,
            is_active=False
        )
        
        featured = CategoryService.get_featured_categories()
        self.assertEqual(featured.count(), 1)  # Solo la activa
    
    def test_get_categories_for_menu(self):
        """Test: Obtener categorías para menú"""
        categories = CategoryService.get_categories_for_menu()
        self.assertEqual(categories.count(), 2)

    def test_get_navbar_items(self):
        """Test: Obtener items de navegación ordenados y activos"""
        from category.models import NavbarItem
        NavbarItem.objects.create(label='Item 2', item_type='custom', custom_url='/2/', position=2, is_active=True)
        NavbarItem.objects.create(label='Item 1', item_type='custom', custom_url='/1/', position=1, is_active=True)
        NavbarItem.objects.create(label='Item Inactivo', item_type='custom', custom_url='/3/', position=3, is_active=False)
        
        items = CategoryService.get_navbar_items()
        self.assertEqual(items.count(), 2)
        self.assertEqual(items[0].label, 'Item 1')
        self.assertEqual(items[1].label, 'Item 2')

    def test_get_category_hierarchy_dict(self):
        """Test: Exportación de jerarquía estructurada de categorías y subcategorías para GEO/AIO"""
        hierarchy = CategoryService.get_category_hierarchy_dict()
        self.assertIsInstance(hierarchy, list)
        self.assertEqual(len(hierarchy), 2)
        
        herramientas = next(item for item in hierarchy if item['name'] == 'Herramientas')
        self.assertEqual(len(herramientas['subcategories']), 2)
        self.assertIn('geo_summary', herramientas)
        self.assertIn('voice_summary', herramientas)
        self.assertIn('subcategories', herramientas)



@pytest.mark.django_db
class TestSubCategoryService(TestCase):
    """Tests para SubCategoryService"""
    
    def setUp(self):
        """Setup para tests del servicio"""
        self.category = Category.objects.create(
            category_name='Herramientas',
            slug='herramientas'
        )
        self.subcategory = SubCategory.objects.create(
            subcategory_name='Destornilladores',
            slug='destornilladores',
            category=self.category
        )
    
    def test_get_subcategory_by_slug_exists(self):
        """Test: Obtener subcategoría por slugs existentes"""
        subcategory = SubCategoryService.get_subcategory_by_slug(
            'herramientas',
            'destornilladores'
        )
        self.assertIsNotNone(subcategory)
        self.assertEqual(subcategory.subcategory_name, 'Destornilladores')
    
    def test_get_subcategory_by_slug_not_exists(self):
        """Test: Obtener subcategoría por slugs inexistentes"""
        subcategory = SubCategoryService.get_subcategory_by_slug(
            'herramientas',
            'no-existe'
        )
        self.assertIsNone(subcategory)
    
    def test_get_subcategories_by_category(self):
        """Test: Obtener subcategorías de una categoría"""
        # Crear otra subcategoría
        SubCategory.objects.create(
            subcategory_name='Martillos',
            slug='martillos',
            category=self.category
        )
        
        subcategories = SubCategoryService.get_subcategories_by_category('herramientas')
        self.assertEqual(subcategories.count(), 2)
    
    def test_get_all_subcategories(self):
        """Test: Obtener todas las subcategorías"""
        # Crear otra categoría y subcategoría
        category2 = Category.objects.create(
            category_name='Electricidad',
            slug='electricidad'
        )
        SubCategory.objects.create(
            subcategory_name='Cables',
            slug='cables',
            category=category2
        )
        
        subcategories = SubCategoryService.get_all_subcategories()
        self.assertEqual(subcategories.count(), 2)

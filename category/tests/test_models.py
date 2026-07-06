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
            
    def test_category_meta_title_fallback_includes_resistencia(self):
        """Verifica que el fallback de meta_title y meta_description incluya texto local."""
        cat = Category.objects.create(
            category_name='Bulones Especiales',
            slug='bulones-especiales',
            description='Bulones de alta resistencia.'
        )
        self.assertEqual(cat.meta_title, "Comprar Bulones Especiales en Resistencia | Stock | Bulonera Alvear")
        self.assertIn("Bulones de alta resistencia.", cat.meta_description)
        self.assertIn("Stock real en Bulonera Alvear", cat.meta_description)
        
    def test_category_rich_description_optional(self):
        """Verifica que rich_description es un campo opcional y guarda contenido HTML."""
        cat = Category.objects.create(
            category_name='Tornillos',
            slug='tornillos',
            rich_description='<h2>Tornillos de todo tipo</h2><p>Texto SEO maestro.</p>'
        )
        self.assertEqual(cat.rich_description, '<h2>Tornillos de todo tipo</h2><p>Texto SEO maestro.</p>')

    def test_category_get_seo_title(self):
        """Verifica el método get_seo_title en Category."""
        # Caso 1: Tiene meta_title explícito
        cat_with_meta = Category.objects.create(
            category_name='Cat 1', slug='cat-1', meta_title='Título Especial'
        )
        self.assertEqual(cat_with_meta.get_seo_title(), 'Título Especial')

        # Caso 2: Sin meta_title (genera fallback truncado dinámicamente)
        cat_no_meta = Category.objects.create(
            category_name='Herramientas Eléctricas Pesadas',
            slug='cat-long'
        )
        cat_no_meta.meta_title = ""
        seo_title = cat_no_meta.get_seo_title()
        self.assertTrue(len(seo_title) <= 60)
        self.assertTrue(seo_title.endswith(" ❘ Bulonera Alvear"))


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
        
    def test_subcategory_meta_title_fallback_includes_resistencia(self):
        """Verifica que el fallback de meta_title y meta_description incluya texto local."""
        sub = SubCategory.objects.create(
            subcategory_name='Clavos',
            slug='clavos',
            category=self.category
        )
        self.assertEqual(sub.meta_title, "Comprar Clavos en Resistencia | Bulonera Alvear")
        self.assertIn("clavos en Chaco", sub.meta_description)
        self.assertIn("Av. Alvear 1301", sub.meta_description)
        
    def test_subcategory_rich_description_optional(self):
        """Verifica que rich_description es un campo opcional y guarda contenido HTML."""
        sub = SubCategory.objects.create(
            subcategory_name='Tuercas',
            slug='tuercas',
            category=self.category,
            rich_description='<p>Tuercas SEO.</p>'
        )
        self.assertEqual(sub.rich_description, '<p>Tuercas SEO.</p>')

    def test_subcategory_get_seo_title(self):
        """Verifica el método get_seo_title en SubCategory."""
        # Caso 1: Tiene meta_title explícito
        sub_with_meta = SubCategory.objects.create(
            subcategory_name='Sub 1', slug='sub-1', category=self.category, meta_title='Título Especial Sub'
        )
        self.assertEqual(sub_with_meta.get_seo_title(), 'Título Especial Sub')

        # Caso 2: Sin meta_title (genera fallback truncado dinámicamente)
        sub_no_meta = SubCategory.objects.create(
            subcategory_name='Destornilladores Articulados Bremen',
            slug='sub-long',
            category=self.category
        )
        sub_no_meta.meta_title = ""
        seo_title = sub_no_meta.get_seo_title()
        self.assertTrue(len(seo_title) <= 60)
        self.assertTrue(seo_title.endswith(" ❘ Bulonera Alvear"))


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


@pytest.mark.django_db
class TestNavbarItemModel(TestCase):
    """Tests para el modelo NavbarItem"""
    
    def setUp(self):
        from category.models import NavbarItem
        self.category = Category.objects.create(
            category_name='Herramientas',
            slug='herramientas'
        )
        self.item_cat = NavbarItem.objects.create(
            label='Herramientas de mano',
            item_type='category',
            category=self.category,
            position=1,
            is_active=True
        )
        self.item_custom = NavbarItem.objects.create(
            label='Google',
            item_type='custom',
            custom_url='https://google.com',
            position=2,
            is_active=True
        )
        self.item_mega = NavbarItem.objects.create(
            label='Menu Completo',
            item_type='mega_menu',
            position=0,
            is_active=True
        )

    def test_navbar_item_creation(self):
        self.assertEqual(self.item_cat.label, 'Herramientas de mano')
        self.assertEqual(self.item_cat.item_type, 'category')
        self.assertEqual(self.item_cat.category, self.category)

    def test_navbar_item_str_representation(self):
        self.assertEqual(str(self.item_cat), 'Herramientas de mano (Categoría del sistema)')
        self.assertEqual(str(self.item_custom), 'Google (Link personalizado)')

    def test_navbar_item_get_url(self):
        self.assertEqual(self.item_cat.get_url(), self.category.get_url())
        self.assertEqual(self.item_custom.get_url(), 'https://google.com')
        self.assertEqual(self.item_mega.get_url(), '#')

    def test_navbar_item_ordering(self):
        from category.models import NavbarItem
        items = list(NavbarItem.objects.all())
        self.assertEqual(items[0], self.item_mega)  # position 0
        self.assertEqual(items[1], self.item_cat)   # position 1
        self.assertEqual(items[2], self.item_custom) # position 2


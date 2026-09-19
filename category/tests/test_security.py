"""
Tests de Seguridad, Sanitización XSS, Validación de URLs y Caching para Category.
"""
import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from rest_framework.test import APIClient
from django.urls import reverse

from category.models import Category, SubCategory, NavbarItem
from category.context_processors import menu_links, CACHE_KEY_MENU_LINKS, CACHE_KEY_NAVBAR_ITEMS


@pytest.mark.django_db
class TestCategoryXSSSanitization:
    """AUD-CAT-002: Verificación de sanitización HTML contra XSS en rich_description."""

    def test_category_rich_description_strips_script_tag(self):
        # Arrange
        dirty_html = "<h2>Bulones de Alta Resistencia</h2><script>alert('xss')</script><p>Párrafo seguro</p>"

        # Act
        cat = Category.objects.create(
            category_name="Tornillos Especiales",
            slug="tornillos-especiales",
            rich_description=dirty_html
        )

        # Assert
        assert "<script>" not in cat.rich_description
        assert "alert('xss')" not in cat.rich_description
        assert "<h2>Bulones de Alta Resistencia</h2>" in cat.rich_description
        assert "<p>Párrafo seguro</p>" in cat.rich_description

    def test_category_rich_description_strips_event_handlers(self):
        # Arrange
        dirty_html = '<p onmouseover="alert(\'steal_token\')">Texto con evento malicioso</p>'

        # Act
        cat = Category.objects.create(
            category_name="Arandelas",
            slug="arandelas",
            rich_description=dirty_html
        )

        # Assert
        assert "onmouseover" not in cat.rich_description
        assert "alert" not in cat.rich_description
        assert "Texto con evento malicioso" in cat.rich_description

    def test_category_rich_description_strips_javascript_url_scheme(self):
        # Arrange
        dirty_html = '<a href="javascript:alert(1)">Click aquí</a>'

        # Act
        cat = Category.objects.create(
            category_name="Tuercas",
            slug="tuercas",
            rich_description=dirty_html
        )

        # Assert
        assert "javascript:" not in cat.rich_description
        assert "Click aquí" in cat.rich_description

    def test_subcategory_rich_description_sanitization(self):
        # Arrange
        cat = Category.objects.create(category_name="Fijaciones", slug="fijaciones")
        dirty_html = '<h3>Subtítulo</h3><iframe src="https://evil.com"></iframe><script>alert(2)</script>'

        # Act
        sub = SubCategory.objects.create(
            subcategory_name="Tarugos",
            slug="tarugos",
            category=cat,
            rich_description=dirty_html
        )

        # Assert
        assert "<iframe" not in sub.rich_description
        assert "<script>" not in sub.rich_description
        assert "<h3>Subtítulo</h3>" in sub.rich_description


@pytest.mark.django_db
class TestNavbarItemURLValidation:
    """AUD-CAT-003: Validación de esquemas seguros en NavbarItem.custom_url."""

    def test_navbar_item_allows_relative_urls(self):
        # Arrange & Act
        item = NavbarItem.objects.create(
            label="Blog",
            item_type="custom",
            custom_url="/blog/",
            position=1
        )

        # Assert
        assert item.get_url() == "/blog/"

    def test_navbar_item_allows_http_and_https_urls(self):
        # Arrange & Act
        item1 = NavbarItem.objects.create(
            label="Google",
            item_type="custom",
            custom_url="https://google.com/search",
            position=1
        )
        item2 = NavbarItem.objects.create(
            label="Sitio Externo",
            item_type="custom",
            custom_url="http://example.com",
            position=2
        )

        # Assert
        assert item1.get_url() == "https://google.com/search"
        assert item2.get_url() == "http://example.com"

    def test_navbar_item_blocks_javascript_scheme(self):
        # Arrange
        item = NavbarItem(
            label="Malicious Link",
            item_type="custom",
            custom_url="javascript:alert(document.cookie)",
            position=1
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            item.clean()
        assert "custom_url" in exc_info.value.message_dict

    def test_navbar_item_blocks_data_scheme(self):
        # Arrange
        item = NavbarItem(
            label="Data URI",
            item_type="custom",
            custom_url="data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
            position=1
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            item.clean()
        assert "custom_url" in exc_info.value.message_dict

    def test_navbar_item_blocks_protocol_relative_urls(self):
        # Arrange
        item = NavbarItem(
            label="Protocol Relative",
            item_type="custom",
            custom_url="//evil.com/phishing",
            position=1
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            item.clean()
        assert "custom_url" in exc_info.value.message_dict


@pytest.mark.django_db
class TestCategoryCachingAndSignals:
    """AUD-CAT-005 & AUD-CAT-007: Caching en context_processors e invalidación vía Signals."""

    def setup_method(self):
        cache.clear()

    def teardown_method(self):
        cache.clear()

    def test_menu_links_populates_and_hits_cache(self):
        # Arrange
        Category.objects.create(category_name="Cat1", slug="cat-1")
        factory = RequestFactory()
        request = factory.get('/')

        # Act - Primer llamado: llena el cache
        context1 = menu_links(request)
        cached_links = cache.get(CACHE_KEY_MENU_LINKS)
        cached_navbar = cache.get(CACHE_KEY_NAVBAR_ITEMS)

        # Assert
        assert cached_links is not None
        assert cached_navbar is not None
        assert len(context1['links']) == 1

        # Act - Segundo llamado: lee del cache
        context2 = menu_links(request)
        assert len(context2['links']) == 1

    def test_category_save_invalidates_cache(self):
        # Arrange
        cache.set(CACHE_KEY_MENU_LINKS, ["cached_item"], timeout=60)
        cache.set(CACHE_KEY_NAVBAR_ITEMS, ["cached_navbar"], timeout=60)

        # Act
        Category.objects.create(category_name="Nueva Cat", slug="nueva-cat")

        # Assert
        assert cache.get(CACHE_KEY_MENU_LINKS) is None
        assert cache.get(CACHE_KEY_NAVBAR_ITEMS) is None

    def test_subcategory_save_invalidates_cache(self):
        # Arrange
        cat = Category.objects.create(category_name="Cat Padre", slug="cat-padre")
        cache.set(CACHE_KEY_MENU_LINKS, ["cached_item"], timeout=60)

        # Act
        SubCategory.objects.create(subcategory_name="Nueva Sub", slug="nueva-sub", category=cat)

        # Assert
        assert cache.get(CACHE_KEY_MENU_LINKS) is None

    def test_navbar_item_save_invalidates_cache(self):
        # Arrange
        cache.set(CACHE_KEY_NAVBAR_ITEMS, ["cached_navbar"], timeout=60)

        # Act
        NavbarItem.objects.create(label="Item", item_type="custom", custom_url="/test/", position=1)

        # Assert
        assert cache.get(CACHE_KEY_NAVBAR_ITEMS) is None


@pytest.mark.django_db
class TestCategoryNPlusOneOptimization:
    """AUD-CAT-004: Verificación de que el listado de categorías evita N+1 en subcategory_count."""

    def test_category_list_api_uses_annotated_count(self):
        # Arrange
        client = APIClient()
        cat1 = Category.objects.create(category_name="Cat1", slug="cat1")
        cat2 = Category.objects.create(category_name="Cat2", slug="cat2")
        SubCategory.objects.create(subcategory_name="Sub1", slug="sub1", category=cat1)
        SubCategory.objects.create(subcategory_name="Sub2", slug="sub2", category=cat1)

        # Act
        url = reverse('category_api:category-list')
        response = client.get(url)

        # Assert
        assert response.status_code == 200
        data = response.data.get('results', response.data)
        cat1_data = next(item for item in data if item['slug'] == 'cat1')
        cat2_data = next(item for item in data if item['slug'] == 'cat2')
        assert cat1_data['subcategory_count'] == 2
        assert cat2_data['subcategory_count'] == 0

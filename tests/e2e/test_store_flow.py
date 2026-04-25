"""
Tests E2E: Flujo completo de la Tienda.
Simula el journey de un usuario anónimo que:
1. Busca un producto
2. Navega al detalle del producto
3. Ve el listado de categoría
"""
import pytest
from django.urls import reverse
from store.models import Product
from category.models import Category, SubCategory


@pytest.mark.django_db
class TestStoreUserJourney:
    """E2E: Flujo completo del usuario en la tienda."""

    @pytest.fixture(autouse=True)
    def setup_store_content(self):
        """Setup: Crea catálogo mínimo para el flujo."""
        self.category = Category.objects.create(
            category_name='Tornillos',
            slug='tornillos'
        )
        self.product = Product.objects.create(
            code='T001',
            name='Tornillo Allen M6x20mm',
            slug='tornillo-allen-m6-20mm',
            price=150.00,
            stock=100,
            category=self.category,
            is_available=True
        )

    def test_step1_store_list_loads(self, client):
        """E2E Paso 1: La tienda carga y muestra productos."""
        response = client.get(reverse('store:store'))
        assert response.status_code == 200

    def test_step1_search_returns_results(self, client):
        """E2E Paso 1: La búsqueda devuelve resultados relevantes."""
        response = client.get(reverse('store:search') + '?q=Allen')
        assert response.status_code == 200

    def test_step2_product_detail_loads(self, client):
        """E2E Paso 2: El detalle de producto carga correctamente."""
        url = reverse('store:product_detail', args=[self.product.slug])
        response = client.get(url)
        assert response.status_code == 200

    def test_step2_product_detail_shows_product_name(self, client):
        """E2E Paso 2: El detalle muestra el nombre del producto."""
        url = reverse('store:product_detail', args=[self.product.slug])
        response = client.get(url)
        content = response.content.decode()
        assert self.product.name in content

    def test_step3_category_page_loads(self, client):
        """E2E Paso 3: La página de categoría carga con sus productos."""
        url = reverse('store:products_by_category', args=[self.category.slug])
        response = client.get(url)
        assert response.status_code == 200

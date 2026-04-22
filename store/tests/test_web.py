import pytest
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
class TestStoreViews:
    """Tests smoke de las vistas HTML de store."""

    def test_home_view_200(self, client):
        """Verifica que la vista home carga con código 200."""
        response = client.get('/')
        assert response.status_code == 200

    def test_store_view_loads(self, client, category, product):
        """Verifica que la vista de tienda carga con código 200."""
        response = client.get(reverse('store:store'))
        assert response.status_code == 200
        assert 'products' in response.context

    def test_store_view_with_category(self, client, category, product):
        """Verifica que la vista filtra por categoría."""
        response = client.get(reverse('store:products_by_category', args=[category.slug]))
        assert response.status_code == 200

    def test_product_detail_view(self, client, product):
        """Verifica que la vista de detalle del producto carga con URL plana (Fase 1)."""
        # URL plana: /store/p/<slug>/
        response = client.get(reverse('store:product_detail', args=[product.slug]))
        assert response.status_code == 200
        assert response.context['single_product'] == product

    def test_product_detail_nonexistent_404(self, client):
        """Verifica que detalle de producto inexistente retorna 404."""
        # URL plana
        response = client.get(reverse('store:product_detail', args=['nonexistent-slug']))
        assert response.status_code == 404

    def test_legacy_product_redirect_301(self, client, product, category):
        """Verifica que URLs legacy redirigen con 301 (Fase 1 - SEO Refactoring)."""
        # URL legacy: /store/category/<cat>/product/<slug>/
        legacy_url = f'/store/category/{category.slug}/product/{product.slug}/'
        
        response = client.get(legacy_url, follow=False)
        assert response.status_code == 301  # Moved Permanently (permanent redirect)
        
        # Verificar que redirige a la URL plana
        new_url = reverse('store:product_detail', args=[product.slug])
        assert new_url in response['Location']

    def test_search_view_without_keyword(self, client):
        """Verifica que search sin keyword devuelve todos los productos."""
        response = client.get(reverse('store:search'))
        # GET sin 'keyword' debería mostrar todos los productos disponibles
        assert response.status_code == 200

    def test_search_view_with_keyword(self, client, product):
        """Verifica que search con keyword filtra correctamente."""
        response = client.get(reverse('store:search') + f"?keyword={product.name[:5]}")
        assert response.status_code == 200
        # La búsqueda debería encontrar el producto
        products = response.context.get('products')
        assert products is not None
        assert len(products) > 0

    def test_search_view_no_results(self, client):
        """Verifica que search con keyword inexistente no retorna errores."""
        response = client.get(reverse('store:search') + "?keyword=xyzinexistente")
        assert response.status_code == 200

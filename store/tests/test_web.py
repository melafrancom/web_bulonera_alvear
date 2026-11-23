import html
import re
from urllib.parse import parse_qs, urlsplit

import pytest
from django.test import Client
from django.urls import reverse
from store.models import Product, ProductTag


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

    def test_store_view_filter_by_tags_and_context(self, client, category):
        """Verifica que la vista de tienda filtra por parámetro GET ?tags y pasa available_tags al context."""
        # Arrange
        tag = ProductTag.objects.create(name="Destacado", slug="destacado")
        p1 = Product.objects.create(
            code='P-WEB-1', name='Producto Destacado', slug='p-web-1',
            price=15.0, stock=5, category=category, is_available=True
        )
        p1.tags.add(tag)
        p2 = Product.objects.create(
            code='P-WEB-2', name='Producto Comun', slug='p-web-2',
            price=25.0, stock=5, category=category, is_available=True
        )

        # Act
        response = client.get(f"{reverse('store:store')}?tags=destacado")

        # Assert
        assert response.status_code == 200
        assert 'available_tags' in response.context
        assert 'tags' in response.context
        assert 'destacado' in response.context['tags']
        p_ids = [p.id for p in response.context['products']]
        assert p1.id in p_ids
        assert p2.id not in p_ids

    def test_store_view_with_category(self, client, category, product):
        """Verifica que la vista filtra por categoría y renderiza rich_description."""
        category.rich_description = "<p>Contenido SEO maestro para categoría.</p>"
        category.save()
        
        response = client.get(reverse('store:products_by_category', args=[category.slug]))
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert "<p>Contenido SEO maestro para categoría.</p>" in content
        assert "Información sobre" in content

    def test_product_detail_view(self, client, product):
        """Verifica que la vista de detalle del producto carga con URL plana (Fase 1)."""
        # URL plana: /store/p/<slug>/
        response = client.get(reverse('store:product_detail', args=[product.slug]))
        assert response.status_code == 200
        assert response.context['single_product'] == product
        
    def test_product_detail_contains_jsonld_product_schema(self, client, product):
        """Verifica que la vista inyecta JSON-LD Product Schema y contiene 'seller'."""
        response = client.get(reverse('store:product_detail', args=[product.slug]))
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert '"@type": "Product"' in content
        assert '"@type": "Offer"' in content
        assert '"seller": {' in content
        assert '"name": "Bulonera Alvear"' in content

    def test_product_detail_renders_related_products_after_description_with_legal_price(self, client, category):
        """Verifica bloque 'Completá tu compra' al final de Descripción, Res. 4/2025, tracking y JSON-LD."""
        from django.core.cache import cache
        from category.models import SubCategory

        cache.clear()
        sub_tuerca = SubCategory.objects.create(
            subcategory_name='Tuercas Hexagonales',
            slug='tuercas-hexagonales',
            category=category,
        )
        bulon = Product.objects.create(
            code='BUL-WEB-6',
            name='Bulón Hexagonal 6 x P 1.0 x 100',
            slug='bulon-web-6',
            description='Descripción técnica del bulón.',
            diameter='6 x P 1.0',
            thread_formats='MA (rosca gruesa)',
            price=121.0,
            stock=10,
            category=category,
            is_available=True,
            diameter_relation='6 x P 1.0',
            thread_formats_relation='MA (rosca gruesa)',
        )
        bulon.related_subcategories.add(sub_tuerca)

        tuerca = Product.objects.create(
            code='TUE-WEB-6',
            name='Tuerca Hexagonal M6 Compatible',
            slug='tuerca-web-6',
            diameter='6 x P 1.0',
            thread_formats='MA (rosca gruesa)',
            price=121.0,
            stock=25,
            category=category,
            is_available=True,
        )
        tuerca.subcategories.add(sub_tuerca)

        response = client.get(reverse('store:product_detail', args=[bulon.slug]))
        assert response.status_code == 200
        content = response.content.decode('utf-8')

        from django.utils.html import escapejs

        assert 'Completá tu compra' in content
        assert 'Tuerca Hexagonal M6 Compatible' in content
        assert 'PRECIO SIN IMPUESTOS NACIONALES: $100,00' in content
        assert f"content_ids: ['{escapejs('TUE-WEB-6')}']" in content
        assert '"isRelatedTo"' in content

        # Ubicación visual: después de Descripción y antes de Reseñas
        desc_pos = content.index('Descripción técnica del bulón.')
        rel_pos = content.index('id="productos-relacionados"')
        rev_pos = content.index('Escribe tu reseña o comentario')
        assert desc_pos < rel_pos < rev_pos

    def test_product_detail_hides_related_section_when_empty(self, client, product):
        """Verifica que la sección 'Completá tu compra' no se renderiza si no hay relacionados."""
        from django.core.cache import cache

        cache.clear()
        response = client.get(reverse('store:product_detail', args=[product.slug]))
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'id="productos-relacionados"' not in content

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
        """Verifica que search con keyword inexistente no retorna errores y pasa keyword al contexto."""
        response = client.get(reverse('store:search') + "?keyword=xyzinexistente")
        assert response.status_code == 200
        assert response.context.get('keyword') == 'xyzinexistente'

    def test_search_view_q_parameter_passes_keyword_to_context(self, client):
        """Verifica que el parámetro estándar 'q' también se pasa al contexto para Empty States."""
        response = client.get(reverse('store:search') + "?q=arandela_especial_123")
        assert response.status_code == 200
        assert response.context.get('keyword') == 'arandela_especial_123'


@pytest.mark.django_db
class TestCommercialEmptyStates:
    def test_zero_search_renders_recovery_cta_and_encodes_query(self, client):
        keyword = "bulon especial 12x1.5"
        response = client.get(reverse("store:search"), {"q": keyword})

        assert response.status_code == 200
        assert keyword in response.content.decode()
        assert "view_zero_search_results" in response.content.decode()
        assert "click_empty_search_whatsapp" in response.content.decode()
        assert f"search_term:'{keyword}'" not in response.content.decode()

        match = re.search(
            r'<a(?=[^>]*data-ba-lead="empty_search")[^>]*href="([^"]+)"',
            response.content.decode(),
        )
        assert match is not None
        href = html.unescape(match.group(1))
        params = parse_qs(urlsplit(href).query)
        assert keyword in params["text"][0]
        assert params["source"] == ["empty_search"]

    def test_filtered_empty_state_has_reset_without_search_copy(self, client):
        from category.models import Category

        empty_category = Category.objects.create(
            category_name="Categoría sin artículos",
            slug="categoria-sin-articulos",
        )
        response = client.get(
            reverse("store:products_by_category", args=[empty_category.slug])
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "No hay productos que coincidan con los filtros seleccionados" in content
        assert "Limpiar filtros y ver catálogo" in content
        assert "No encontramos productos para" not in content


class TestTemplateSyntaxIntegrity:
    """Valida la integridad y compilación sintáctica de cada plantilla física del proyecto."""

    def test_all_project_templates_compile_without_syntax_errors(self):
        """
        QUÉ: Recorre cada archivo físico .html bajo las raíces de los loaders del proyecto y compila su AST.
        POR QUÉ: Garantiza ausencia de tags huérfanos, filtros inválidos o errores de herencia antes del deploy.
        NOTA: Esta prueba valida compilación sintáctica; la validación de contextos y renderizado efectivo
              se verifica mediante los tests de vistas web con client.get().
        """
        import os
        from django.conf import settings
        from django.template import engines, Template
        from django.template.base import Origin
        from django.template.exceptions import TemplateSyntaxError, TemplateDoesNotExist

        base_dir_str = str(settings.BASE_DIR)
        compiled_count = 0
        template_errors = []

        for engine in engines.all():
            django_engine = getattr(engine, 'engine', None)
            if not django_engine:
                continue
            loaders = getattr(django_engine, 'template_loaders', [])
            for loader in loaders:
                if not hasattr(loader, 'get_dirs'):
                    continue
                for directory in loader.get_dirs():
                    dir_path = str(directory)
                    if not dir_path.startswith(base_dir_str):
                        continue
                    for root, _, files in os.walk(dir_path):
                        for f in files:
                            if f.endswith('.html'):
                                full_path = os.path.join(root, f)
                                rel_path = os.path.relpath(full_path, base_dir_str)
                                try:
                                    with open(full_path, 'r', encoding='utf-8') as fp:
                                        content = fp.read()
                                    Template(content, origin=Origin(full_path), engine=django_engine)
                                    compiled_count += 1
                                except (TemplateSyntaxError, TemplateDoesNotExist) as exc:
                                    template_errors.append(f"{rel_path}: {exc}")

        assert compiled_count > 0, "No se encontraron archivos de plantilla para compilar en el proyecto."
        assert len(template_errors) == 0, (
            f"Errores de sintaxis detectados en templates ({len(template_errors)}):\n"
            + "\n".join(template_errors)
        )


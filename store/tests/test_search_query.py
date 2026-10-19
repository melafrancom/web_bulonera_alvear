"""
Tests unitarios e integrales para SearchService, SearchQuery y telemetría de demanda oculta (Parte 1).

Cubre:
1. Búsqueda por categoría y subcategoría en SearchService.search_products (con deduplicación .distinct()).
2. Heurística de reducción de riesgo PII (emails, documentos, teléfonos locales y nacionales).
3. Casos comerciales negativos de PII (medidas técnicas 12x1.5, 14x2 100, 3/8) que sí son admitidos.
4. Trade-off documentado de códigos SKU numéricos de 7 a 11 dígitos sin coincidencia.
5. Higiene de logs (sin volcado de términos crudos).
6. Inmutabilidad en Django Admin (has_add_permission=False, has_delete_permission=False).
"""
import pytest
from decimal import Decimal
from django.urls import reverse
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from store.models import SearchQuery, Product
from store.services import SearchService
from store.admin import SearchQueryAdmin
from category.models import Category, SubCategory


@pytest.fixture
def catalog_setup(db):
    """Fixture con taxonomía real (Bulonería y Ferretería) y productos asociados"""
    cat_buloneria = Category.objects.create(
        category_name='Bulonería',
        slug='buloneria'
    )
    subcat_comun = SubCategory.objects.create(
        category=cat_buloneria,
        subcategory_name='bulon comun',
        slug='bulon-comun'
    )
    subcat_g5 = SubCategory.objects.create(
        category=cat_buloneria,
        subcategory_name='bulon G5 alta resistencia',
        slug='bulon-g5-alta-resistencia'
    )
    
    prod1 = Product.objects.create(
        name='Bulon Hexagonal Zincado 1/2 x 2',
        slug='bulon-hexagonal-zincado-1-2-x-2',
        code='00100100001',
        price=Decimal('250.00'),
        stock=100,
        is_available=True,
        category=cat_buloneria
    )
    prod1.subcategories.add(subcat_comun)

    prod2 = Product.objects.create(
        name='Bulon Grado 5 SAE Cabeza Hexagonal',
        slug='bulon-grado-5-sae-cabeza-hexagonal',
        code='00100100002',
        price=Decimal('450.00'),
        stock=50,
        is_available=True,
        category=cat_buloneria
    )
    prod2.subcategories.add(subcat_g5)

    return {
        'category': cat_buloneria,
        'subcat_comun': subcat_comun,
        'subcat_g5': subcat_g5,
        'prod1': prod1,
        'prod2': prod2,
    }


class TestSearchProductsRelational:
    """Pruebas de búsqueda relacional por categoría, subcategoría y deduplicación"""

    def test_search_by_exact_category_name(self, catalog_setup):
        results = SearchService.search_products('Bulonería')
        assert results.count() == 2
        assert catalog_setup['prod1'] in results
        assert catalog_setup['prod2'] in results

    def test_search_by_unaccented_category_name(self, catalog_setup):
        """Comprueba que en MariaDB utf8mb4_spanish_ci 'buloneria' coincida con 'Bulonería' devolviendo ambos productos"""
        results = SearchService.search_products('buloneria')
        assert results.count() == 2
        assert catalog_setup['prod1'] in results
        assert catalog_setup['prod2'] in results

    def test_search_by_subcategory_name(self, catalog_setup):
        results = SearchService.search_products('bulon comun')
        assert results.count() == 1
        assert results.first() == catalog_setup['prod1']

    def test_search_by_partial_subcategory_name(self, catalog_setup):
        results = SearchService.search_products('G5 alta resistencia')
        assert results.count() == 1
        assert results.first() == catalog_setup['prod2']

    def test_search_deduplication_with_distinct(self, catalog_setup):
        """Verifica que un producto asociado a múltiples subcategorías no aparezca duplicado"""
        prod = catalog_setup['prod1']
        prod.subcategories.add(catalog_setup['subcat_g5'])

        results = SearchService.search_products('bulon')
        # Ambos productos tienen 'bulon' en su nombre y categoría, no debe haber duplicados
        pks = list(results.values_list('pk', flat=True))
        assert len(pks) == len(set(pks))

    def test_search_by_numeric_sku(self, catalog_setup):
        """Verifica que códigos comerciales numéricos de 11 dígitos sean buscados en el catálogo"""
        results = SearchService.search_products('00100100001')
        assert results.count() == 1
        assert results.first() == catalog_setup['prod1']


class TestPIIHeuristicsAndTradeoffs:
    """Pruebas de la heurística anti-PII y validación de casos comerciales permitidos"""

    @pytest.mark.parametrize("pii_query", [
        "consulta juan@gmail.com",
        "pedidos contacto@empresa.com.ar",
        "mi dni es 35123456",
        "cliente 35.123.456",
        "cuit 20-35123456-4",
        "cuit 20 35123456 4",
        "telefono 473-3431",
        "contacto 473 3431",
        "whatsapp +54 9 362 4733431",
        "llamar a 3624733431",
        "0362 15 4733431",
    ])
    def test_sensitive_pii_patterns_are_detected(self, pii_query):
        assert SearchService.contains_sensitive_pii(pii_query) is True

    @pytest.mark.parametrize("commercial_query", [
        "bulon 12x1.5",
        "tornillo 14x2 100",
        "varilla 3/8 1000mm",
        "mecha copa 35mm bahco",
        "din 933 8.8 m12x50",
        "arandela grower 5/16",
        "tirafondo 1/4 x 3",
    ])
    def test_commercial_measures_are_not_discarded(self, commercial_query):
        """Verifica que combinaciones numéricas de ferretería NO sean falsos positivos de PII"""
        assert SearchService.contains_sensitive_pii(commercial_query) is False

    def test_documented_tradeoff_for_unmatched_pure_numeric_skus(self):
        """
        TRADE-OFF DOCUMENTADO: Códigos numéricos de 7 a 11 dígitos sin letras que NO
        existen en el catálogo son descartados por la heurística de telemetría para
        prevenir la persistencia involuntaria de DNIs o números telefónicos.
        """
        unmatched_numeric_sku = "00100999999"
        # Coincide con _RE_DOC_STANDALONE (\b\d{7,11}\b)
        assert SearchService.contains_sensitive_pii(unmatched_numeric_sku) is True


class TestSearchQueryTelemetry:
    """Pruebas unitarias de SearchService.record_unmatched_search y SearchQuery"""

    def test_record_unmatched_commercial_term(self, db):
        SearchService.record_unmatched_search('disco flap 115 grano 60')
        
        record = SearchQuery.objects.filter(query_text='disco flap 115 grano 60').first()
        assert record is not None
        assert record.search_count == 1
        assert str(record) == 'disco flap 115 grano 60 (1 búsquedas)'

    def test_record_unmatched_increments_request_counter(self, db):
        SearchService.record_unmatched_search('mecha escalonada 4-32')
        SearchService.record_unmatched_search('  Mecha Escalonada 4-32  ')
        
        record = SearchQuery.objects.get(query_text='mecha escalonada 4-32')
        assert record.search_count == 2

    def test_record_unmatched_ignores_short_or_empty_terms(self, db):
        SearchService.record_unmatched_search('')
        SearchService.record_unmatched_search('   ')
        SearchService.record_unmatched_search('ab')
        SearchService.record_unmatched_search(None)

        assert SearchQuery.objects.count() == 0

    def test_record_unmatched_discards_pii(self, db):
        SearchService.record_unmatched_search('consultas martin@yahoo.com')
        SearchService.record_unmatched_search('mi telefono es 473-3431')
        SearchService.record_unmatched_search('dni 32123456')

        assert SearchQuery.objects.count() == 0

    @pytest.mark.parametrize("commercial_query", [
        "bulon 12x1.5",
        "tornillo 14x2 100",
        "varilla 3/8 1000mm",
        "mecha copa 35mm bahco",
        "din 933 8.8 m12x50",
        "arandela grower 5/16",
        "tirafondo 1/4 x 3",
    ])
    def test_record_unmatched_persists_commercial_measures(self, db, commercial_query):
        """Verifica que las medidas y códigos comerciales de ferretería efectivamente se persistan en SearchQuery"""
        SearchService.record_unmatched_search(commercial_query)
        assert SearchQuery.objects.filter(query_text=commercial_query.lower()).exists()

    def test_record_unmatched_unifies_100_character_limit_with_search_products(self, db):
        """Verifica que el término persistido se trunque exactamente a 100 caracteres, igual que en search_products"""
        long_query = "a" * 150
        SearchService.record_unmatched_search(long_query)
        record = SearchQuery.objects.first()
        assert record is not None
        assert len(record.query_text) == 100
        assert record.query_text == "a" * 100

    def test_record_unmatched_detects_pii_near_or_across_boundary(self, db):
        """Verifica que un dato sensible situado cerca del límite de 100 caracteres sea detectado antes de truncar"""
        padding = "herramienta manual para taller " * 3  # 93 caracteres
        pii_query = padding + "juan@empresa.com"
        SearchService.record_unmatched_search(pii_query)
        # Debe descartarse en su totalidad sin guardar fragmentos truncados
        assert SearchQuery.objects.count() == 0


class TestSearchQueryIntegration:
    """Pruebas de integración en la vista web de búsqueda"""

    def test_search_view_records_unmatched_query_without_pii(self, client, db):
        url = reverse('store:search')
        response = client.get(url, {'q': 'amoladora angular 9 pulgadas'})
        assert response.status_code == 200

        record = SearchQuery.objects.filter(query_text='amoladora angular 9 pulgadas').first()
        assert record is not None
        assert record.search_count == 1

    def test_search_view_does_not_record_unmatched_with_pii(self, client, db):
        url = reverse('store:search')
        response = client.get(url, {'q': 'pedido de juan@hotmail.com urgente'})
        assert response.status_code == 200

        assert SearchQuery.objects.count() == 0

    def test_search_view_does_not_record_unmatched_when_results_exist(self, client, catalog_setup):
        url = reverse('store:search')
        response = client.get(url, {'q': 'Bulonería'})
        assert response.status_code == 200
        assert catalog_setup['prod1'] in response.context['products']

        # No debe haber creado entrada en SearchQuery
        assert SearchQuery.objects.count() == 0


class TestSearchQueryAdminPermissions:
    """Pruebas de inmutabilidad en Django Admin"""

    def test_admin_disallows_add_and_delete(self, rf):
        site = AdminSite()
        admin_instance = SearchQueryAdmin(SearchQuery, site)
        request = rf.get('/admin/')

        assert admin_instance.has_add_permission(request) is False
        assert admin_instance.has_delete_permission(request) is False

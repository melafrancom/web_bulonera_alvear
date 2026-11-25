"""
Tests unitarios e integrales para SearchService, SearchQuery, SearchQueryDaily y exportación Excel.

Cubre:
1. Búsqueda por categoría y subcategoría en SearchService.search_products (con deduplicación .distinct()).
2. Heurística de reducción de riesgo PII (emails, documentos, teléfonos locales y nacionales) y casos ferreteros permitidos.
3. Registro unificado (con y sin resultados), transiciones de cobertura, colapsado de espacios y guard anti-bots.
4. Agregación por ventana temporal (7, 30, 90 días y todo el histórico) con SearchQueryDaily.
5. Exportación Excel en streaming (2 hojas, ranking, formato '@' en medidas, anti Formula Injection CWE-1236, queryset vacío).
6. Django Admin: descarga segura, filtros, acción masiva, permisos 403/405, detalle >90d sin 404 e inmutabilidad.
"""
import importlib
import io
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import openpyxl
import pytest
from django.apps import apps
from django.contrib.admin.sites import AdminSite
from django.core.cache import cache
from django.http import QueryDict
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from account.models import Account
from category.models import Category, SubCategory
from store.admin import SearchQueryAdmin
from store.models import Product, ProductSearch, SearchQuery, SearchQueryDaily
from store.services import ProductService, SearchService
from store.templatetags.store_filters import query_with_page


@pytest.fixture(autouse=True)
def clear_search_cache():
    """Aísla contadores de rate-limiting en caché entre tests."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def catalog_setup(db):
    """Fixture con taxonomía real (Bulonería) y productos asociados."""
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


@pytest.fixture
def staff_viewer_client(db, admin_user):
    """Cliente autenticado como admin autorizado sobre el panel de SearchQuery."""
    c = Client()
    c.force_login(admin_user)
    return c


@pytest.fixture
def staff_no_perm_client(db):
    """Cliente autenticado como staff activo sin permisos de administrador sobre SearchQuery."""
    user = Account.objects.create_user(
        first_name='Operador',
        last_name='Limitado',
        username='operador_limitado',
        email='operador_limitado@bulonera.test',
        password='TestPassword123!'
    )
    user.is_staff = True
    user.is_admin = False
    user.is_superadmin = False
    user.is_active = True
    user.save()

    c = Client()
    c.force_login(user)
    return c


class TestSearchProductsRelational:
    """Pruebas de búsqueda relacional por categoría, subcategoría y deduplicación."""

    def test_search_by_exact_category_name(self, catalog_setup):
        results = SearchService.search_products('Bulonería')
        assert results.count() == 2
        assert catalog_setup['prod1'] in results
        assert catalog_setup['prod2'] in results

    def test_search_by_unaccented_category_name(self, catalog_setup):
        """Comprueba que en MariaDB utf8mb4_spanish_ci 'buloneria' coincida con 'Bulonería'."""
        from django.db import connection
        if connection.vendor == 'sqlite':
            pytest.skip("Requiere colación utf8mb4_spanish_ci nativa de MariaDB para insensibilidad a tildes")
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
        """Verifica que un producto asociado a múltiples subcategorías no aparezca duplicado."""
        prod = catalog_setup['prod1']
        prod.subcategories.add(catalog_setup['subcat_g5'])

        results = SearchService.search_products('bulon')
        pks = list(results.values_list('pk', flat=True))
        assert len(pks) == len(set(pks))

    def test_search_by_numeric_sku(self, catalog_setup):
        """Verifica que códigos comerciales numéricos de 11 dígitos sean buscados en el catálogo."""
        results = SearchService.search_products('00100100001')
        assert results.count() == 1
        assert results.first() == catalog_setup['prod1']


class TestPIIHeuristicsAndTradeoffs:
    """Pruebas de la heurística anti-PII y validación de casos comerciales permitidos."""

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
        """Verifica que combinaciones numéricas de ferretería NO sean falsos positivos de PII."""
        assert SearchService.contains_sensitive_pii(commercial_query) is False

    def test_documented_tradeoff_for_unmatched_pure_numeric_skus(self):
        """
        TRADE-OFF DOCUMENTADO: Códigos numéricos de 7 a 11 dígitos sin letras que NO
        existen en el catálogo son descartados por la heurística de telemetría.
        """
        unmatched_numeric_sku = "00100999999"
        assert SearchService.contains_sensitive_pii(unmatched_numeric_sku) is True


class TestSearchQueryTelemetry:
    """Pruebas unitarias de SearchService.record_search_query, wrapper y guards."""

    def test_record_unmatched_commercial_term(self, db):
        SearchService.record_unmatched_search('disco flap 115 grano 60')

        record = SearchQuery.objects.filter(query_text='disco flap 115 grano 60').first()
        assert record is not None
        assert record.search_count == 1
        assert record.unmatched_count == 1
        assert record.matched_count == 0
        assert record.last_results_count == 0
        assert record.has_results is False
        assert str(record) == 'disco flap 115 grano 60 (1 búsquedas)'

        daily = SearchQueryDaily.objects.get(search_query=record, date=timezone.localdate())
        assert daily.unmatched_count == 1
        assert daily.matched_count == 0

    def test_record_unmatched_increments_request_counter(self, db):
        SearchService.record_unmatched_search('mecha escalonada 4-32')
        SearchService.record_unmatched_search('  Mecha   Escalonada   4-32  ')

        record = SearchQuery.objects.get(query_text='mecha escalonada 4-32')
        assert record.search_count == 2
        assert record.unmatched_count == 2
        assert record.matched_count == 0

    def test_record_matched_and_coverage_transitions(self, db):
        # 1. Empieza sin resultados (demanda oculta)
        SearchService.record_search_query('bulon inoxidable 1/4', results_count=0)
        record = SearchQuery.objects.get(query_text='bulon inoxidable 1/4')
        assert record.has_results is False
        assert record.unmatched_count == 1
        assert record.matched_count == 0

        # 2. Se carga el producto -> pasa a tener resultados
        SearchService.record_search_query('bulon inoxidable 1/4', results_count=4)
        record.refresh_from_db()
        assert record.search_count == 2
        assert record.unmatched_count == 1
        assert record.matched_count == 1
        assert record.last_results_count == 4
        assert record.has_results is True

        # 3. Quiebre de stock -> vuelve a 0 resultados
        SearchService.record_search_query('bulon inoxidable 1/4', results_count=0)
        record.refresh_from_db()
        assert record.search_count == 3
        assert record.unmatched_count == 2
        assert record.matched_count == 1
        assert record.last_results_count == 0
        assert record.has_results is False

    def test_record_ignores_short_or_empty_terms(self, db):
        SearchService.record_search_query('', results_count=5)
        SearchService.record_search_query('   ', results_count=0)
        SearchService.record_search_query('ab', results_count=2)
        SearchService.record_search_query(None, results_count=0)

        assert SearchQuery.objects.count() == 0

    def test_record_discards_pii_for_both_matched_and_unmatched(self, db):
        SearchService.record_search_query('consultas martin@yahoo.com', results_count=3)
        SearchService.record_search_query('mi telefono es 473-3431', results_count=0)
        SearchService.record_search_query('dni 32123456', results_count=10)

        assert SearchQuery.objects.count() == 0

    @pytest.mark.parametrize("bot_ua", [
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "WhatsApp/2.23.20.0 A",
        "python-requests/2.31.0",
        "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
        "Mozilla/5.0 (compatible; GPTBot/1.0; +https://openai.com/gptbot)",
    ])
    def test_bot_user_agents_are_discarded(self, db, bot_ua):
        assert SearchService.is_bot_user_agent(bot_ua) is True
        SearchService.record_search_query('tornillo autoperforante', results_count=5, user_agent=bot_ua)
        assert SearchQuery.objects.count() == 0

    def test_empty_user_agent_is_allowed(self, db):
        assert SearchService.is_bot_user_agent('') is False
        assert SearchService.is_bot_user_agent(None) is False
        SearchService.record_search_query('tornillo autoperforante', results_count=5, user_agent='')
        assert SearchQuery.objects.filter(query_text='tornillo autoperforante').exists()

    @pytest.mark.parametrize("commercial_query", [
        "bulon 12x1.5",
        "tornillo 14x2 100",
        "varilla 3/8 1000mm",
        "mecha copa 35mm bahco",
        "din 933 8.8 m12x50",
        "arandela grower 5/16",
        "tirafondo 1/4 x 3",
    ])
    def test_record_persists_commercial_measures(self, db, commercial_query):
        SearchService.record_unmatched_search(commercial_query)
        assert SearchQuery.objects.filter(query_text=commercial_query.lower()).exists()

    def test_record_unifies_100_character_limit_with_search_products(self, db):
        long_query = "a" * 150
        SearchService.record_search_query(long_query, results_count=1)
        record = SearchQuery.objects.first()
        assert record is not None
        assert len(record.query_text) == 100
        assert record.query_text == "a" * 100

    def test_record_detects_pii_near_or_across_boundary(self, db):
        padding = "herramienta manual para taller " * 3
        pii_query = padding + "juan@empresa.com"
        SearchService.record_search_query(pii_query, results_count=2)
        assert SearchQuery.objects.count() == 0


class TestSearchQueryPeriodRanking:
    """Pruebas de ventanas temporales (7, 30, 90 días y todo el histórico)."""

    def test_resolve_period_days_defaults_to_90(self):
        assert SearchService.resolve_period_days(None) == 90
        assert SearchService.resolve_period_days('90') == 90
        assert SearchService.resolve_period_days('30') == 30
        assert SearchService.resolve_period_days('7') == 7
        assert SearchService.resolve_period_days('all') is None
        assert SearchService.resolve_period_days('invalid') == 90

    def test_apply_period_ranking_aggregates_by_window(self, db):
        today = timezone.localdate()
        sq = SearchQuery.objects.create(
            query_text='llave tubo 1/2',
            search_count=15,
            matched_count=10,
            unmatched_count=5,
            last_results_count=3,
        )
        # Hoy: 1 match, 1 unmatch (total=2)
        SearchQueryDaily.objects.create(search_query=sq, date=today, matched_count=1, unmatched_count=1, last_results_count=3)
        # Hace 20 días: 2 match, 1 unmatch (total=3)
        SearchQueryDaily.objects.create(search_query=sq, date=today - timedelta(days=20), matched_count=2, unmatched_count=1, last_results_count=3)
        # Hace 60 días: 3 match, 1 unmatch (total=4)
        SearchQueryDaily.objects.create(search_query=sq, date=today - timedelta(days=60), matched_count=3, unmatched_count=1, last_results_count=3)
        # Hace 120 días: 4 match, 2 unmatch (total=6)
        SearchQueryDaily.objects.create(search_query=sq, date=today - timedelta(days=120), matched_count=4, unmatched_count=2, last_results_count=3)

        row_7 = SearchService.apply_period_ranking(SearchQuery.objects.all(), period_days=7).get(pk=sq.pk)
        assert row_7.period_total == 2

        row_30 = SearchService.apply_period_ranking(SearchQuery.objects.all(), period_days=30).get(pk=sq.pk)
        assert row_30.period_total == 5

        row_90 = SearchService.apply_period_ranking(SearchQuery.objects.all(), period_days=90).get(pk=sq.pk)
        assert row_90.period_total == 9
        assert row_90.period_matched == 6
        assert row_90.period_unmatched == 3

        row_all = SearchService.apply_period_ranking(SearchQuery.objects.all(), period_days=None).get(pk=sq.pk)
        assert row_all.period_total == 15


class TestSearchQueryExcelExport:
    """Pruebas del exportador Excel en streaming y protección anti-Formula Injection."""

    def test_export_workbook_structure_ranking_and_measures(self, db):
        today = timezone.localdate()

        # Término antiguo con gran acumulado histórico pero poca actividad reciente
        sq_old = SearchQuery.objects.create(
            query_text='tuerca 3/8',
            search_count=55,
            matched_count=55,
            unmatched_count=0,
            last_results_count=12,
        )
        SearchQueryDaily.objects.create(
            search_query=sq_old, date=today - timedelta(days=120), matched_count=50, unmatched_count=0, last_results_count=12
        )
        SearchQueryDaily.objects.create(
            search_query=sq_old, date=today - timedelta(days=5), matched_count=5, unmatched_count=0, last_results_count=12
        )

        # Término sin resultados líder en los últimos 90 días
        sq_hot = SearchQuery.objects.create(
            query_text='mecha 1/4',
            search_count=12,
            matched_count=0,
            unmatched_count=12,
            last_results_count=0,
        )
        SearchQueryDaily.objects.create(
            search_query=sq_hot, date=today - timedelta(days=10), matched_count=0, unmatched_count=12, last_results_count=0
        )

        buffer = SearchService.export_search_queries_workbook(period_days=90)
        wb = openpyxl.load_workbook(io.BytesIO(buffer.read()))

        assert wb.sheetnames == ['Ranking', 'Resumen']

        ws_rank = wb['Ranking']
        headers = [ws_rank.cell(row=1, column=i).value for i in range(1, 12)]
        assert headers == [
            'ranking', 'termino_buscado', 'estado_actual', 'busquedas_periodo',
            'sin_resultado_periodo', 'con_resultado_periodo', 'tasa_sin_resultado',
            'resultados_actuales', 'total_historico', 'accion_sugerida', 'ultima_busqueda',
        ]

        # Fila 2: líder en los últimos 90 días ('mecha 1/4' con 12 > 'tuerca 3/8' con 5)
        assert ws_rank.cell(row=2, column=1).value == 1
        term_cell_1 = ws_rank.cell(row=2, column=2)
        assert term_cell_1.value == 'mecha 1/4'
        assert term_cell_1.number_format == '@'
        assert ws_rank.cell(row=2, column=3).value == 'Sin resultados'
        assert ws_rank.cell(row=2, column=4).value == 12
        assert ws_rank.cell(row=2, column=10).value == 'Incorporar producto / sinónimo prioritario'

        # Fila 3: 'tuerca 3/8' con solo 5 búsquedas en la ventana de 90d (excluyendo las 50 de hace 120d)
        assert ws_rank.cell(row=3, column=1).value == 2
        term_cell_2 = ws_rank.cell(row=3, column=2)
        assert term_cell_2.value == 'tuerca 3/8'
        assert term_cell_2.number_format == '@'
        assert ws_rank.cell(row=3, column=4).value == 5
        assert ws_rank.cell(row=3, column=9).value == 55

        ws_summary = wb['Resumen']
        summary_dict = {
            ws_summary.cell(row=r, column=1).value: ws_summary.cell(row=r, column=2).value
            for r in range(1, ws_summary.max_row + 1)
            if ws_summary.cell(row=r, column=1).value
        }
        assert summary_dict['Ventana analizada'] == 'Últimos 90 días'
        assert summary_dict['Términos únicos exportados'] == 2
        assert summary_dict['Búsquedas totales del período'] == 17
        assert summary_dict['Búsquedas con resultado'] == 5
        assert summary_dict['Búsquedas sin resultado'] == 12

    @pytest.mark.parametrize("payload", [
        "=1+1",
        "+cmd|' /C calc'!A0",
        "-2+3",
        "@SUM(A1:A2)",
        "\t=1+1",
    ])
    def test_export_neutralizes_formula_injection(self, db, payload):
        today = timezone.localdate()
        sq = SearchQuery.objects.create(query_text=payload, search_count=1, unmatched_count=1)
        SearchQueryDaily.objects.create(search_query=sq, date=today, unmatched_count=1)

        buffer = SearchService.export_search_queries_workbook(period_days=90)
        wb = openpyxl.load_workbook(io.BytesIO(buffer.read()))
        ws = wb['Ranking']
        cell = ws.cell(row=2, column=2)
        assert cell.data_type == 's'
        assert cell.number_format == '@'

    def test_export_empty_queryset_succeeds(self, db):
        buffer = SearchService.export_search_queries_workbook(
            queryset=SearchQuery.objects.none(),
            period_days=90,
        )
        wb = openpyxl.load_workbook(io.BytesIO(buffer.read()))
        assert wb.sheetnames == ['Ranking', 'Resumen']
        assert wb['Ranking'].max_row == 1


class TestSearchQueryIntegration:
    """Pruebas de integración en la vista web de búsqueda."""

    def test_search_view_records_unmatched_query_without_pii(self, client, db):
        url = reverse('store:search')
        response = client.get(url, {'q': 'amoladora angular 9 pulgadas'})
        assert response.status_code == 200

        record = SearchQuery.objects.filter(query_text='amoladora angular 9 pulgadas').first()
        assert record is not None
        assert record.search_count == 1
        assert record.unmatched_count == 1
        assert record.matched_count == 0
        assert record.last_results_count == 0

    def test_search_view_does_not_record_unmatched_with_pii(self, client, db):
        url = reverse('store:search')
        response = client.get(url, {'q': 'pedido de juan@hotmail.com urgente'})
        assert response.status_code == 200

        assert SearchQuery.objects.count() == 0

    def test_search_view_records_matched_query_and_daily_metrics(self, client, catalog_setup):
        url = reverse('store:search')
        response = client.get(url, {'q': 'Bulonería'})
        assert response.status_code == 200
        assert catalog_setup['prod1'] in response.context['products']

        record = SearchQuery.objects.filter(query_text='bulonería').first()
        assert record is not None
        assert record.search_count == 1
        assert record.matched_count == 1
        assert record.unmatched_count == 0
        assert record.last_results_count == 2
        assert record.has_results is True

        daily = SearchQueryDaily.objects.get(search_query=record, date=timezone.localdate())
        assert daily.matched_count == 1
        assert daily.unmatched_count == 0


class TestSearchQueryAdminPermissionsAndExport:
    """Pruebas de inmutabilidad, permisos, filtros y exportación Excel en Django Admin."""

    def test_admin_disallows_add_and_delete(self, rf):
        site = AdminSite()
        admin_instance = SearchQueryAdmin(SearchQuery, site)
        request = rf.get('/admin/')

        assert admin_instance.has_add_permission(request) is False
        assert admin_instance.has_delete_permission(request) is False

    def test_admin_export_excel_respects_filters_and_returns_xlsx(self, staff_viewer_client):
        today = timezone.localdate()
        sq_unmatched = SearchQuery.objects.create(
            query_text='llave stilson 18', search_count=8, unmatched_count=8, last_results_count=0
        )
        SearchQueryDaily.objects.create(search_query=sq_unmatched, date=today, unmatched_count=8, last_results_count=0)

        sq_matched = SearchQuery.objects.create(
            query_text='bulon hexagonal', search_count=15, matched_count=15, last_results_count=4
        )
        SearchQueryDaily.objects.create(search_query=sq_matched, date=today, matched_count=15, last_results_count=4)

        url = reverse('admin:store_searchquery_export_excel')
        response = staff_viewer_client.get(url, {'period': '90', 'status': 'unmatched', 'q': 'stilson'})
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

        content = b''.join(response.streaming_content)
        wb = openpyxl.load_workbook(io.BytesIO(content))
        ws = wb['Ranking']
        assert ws.max_row == 2
        assert ws.cell(row=2, column=2).value == 'llave stilson 18'

    def test_admin_export_excel_forbids_unauthorized_staff_and_rejects_post(
        self, staff_no_perm_client, staff_viewer_client
    ):
        url = reverse('admin:store_searchquery_export_excel')
        assert staff_no_perm_client.get(url).status_code == 403
        assert staff_viewer_client.post(url).status_code == 405

    def test_admin_bulk_action_exports_selected_queries(self, staff_viewer_client):
        today = timezone.localdate()
        sq1 = SearchQuery.objects.create(query_text='arandela plana 1/2', search_count=4, matched_count=4, last_results_count=2)
        SearchQueryDaily.objects.create(search_query=sq1, date=today, matched_count=4, last_results_count=2)

        sq2 = SearchQuery.objects.create(query_text='tarugo fisher 8mm', search_count=9, unmatched_count=9, last_results_count=0)
        SearchQueryDaily.objects.create(search_query=sq2, date=today, unmatched_count=9, last_results_count=0)

        changelist_url = reverse('admin:store_searchquery_changelist')
        response = staff_viewer_client.post(
            changelist_url,
            {
                'action': 'export_selected_queries_excel',
                '_selected_action': [str(sq1.pk)],
            },
        )
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

        content = b''.join(response.streaming_content)
        wb = openpyxl.load_workbook(io.BytesIO(content))
        ws = wb['Ranking']
        assert ws.max_row == 2
        assert ws.cell(row=2, column=2).value == 'arandela plana 1/2'

    def test_admin_readonly_detail_accessible_for_records_older_than_90_days(self, staff_viewer_client):
        old_date = timezone.localdate() - timedelta(days=180)
        sq_old = SearchQuery.objects.create(
            query_text='electrodo 6013 2.5mm', search_count=3, unmatched_count=3, last_results_count=0
        )
        SearchQueryDaily.objects.create(search_query=sq_old, date=old_date, unmatched_count=3, last_results_count=0)

        change_url = reverse('admin:store_searchquery_change', args=[sq_old.pk])
        response = staff_viewer_client.get(change_url)
        assert response.status_code == 200
        assert 'electrodo 6013 2.5mm' in response.content.decode('utf-8')

    def test_admin_export_excel_malformed_params_fallback_safely(self, staff_viewer_client):
        today = timezone.localdate()
        sq = SearchQuery.objects.create(query_text='mecha widia 8mm', search_count=4, matched_count=4, last_results_count=2)
        SearchQueryDaily.objects.create(search_query=sq, date=today, matched_count=4, last_results_count=2)

        url = reverse('admin:store_searchquery_export_excel')
        response = staff_viewer_client.get(url, {'period': 'bogus', 'status': 'unknown'})
        assert response.status_code == 200
        assert response['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

        wb = openpyxl.load_workbook(io.BytesIO(b''.join(response.streaming_content)))
        ws_summary = wb['Resumen']
        summary = {
            ws_summary.cell(row=r, column=1).value: ws_summary.cell(row=r, column=2).value
            for r in range(1, ws_summary.max_row + 1)
            if ws_summary.cell(row=r, column=1).value
        }
        assert summary['Ventana analizada'] == 'Últimos 90 días'
        assert summary['Filtro de cobertura'] == 'Todos (con y sin resultados)'


class TestSearchPaginationAndSorting:
    """Pruebas de paginación en store:search, preservación de parámetros y sort_by."""

    def test_search_view_paginates_to_30_and_skips_telemetry_on_page_2_and_out_of_range(
        self, client, catalog_setup
    ):
        cat = catalog_setup['category']
        for i in range(33):
            Product.objects.create(
                name=f'Bulon Industrial Serie {i:02d}',
                slug=f'bulon-industrial-serie-{i:02d}',
                code=f'BUL-PAG-{i:02d}',
                price=Decimal('100.00') + i,
                stock=10,
                is_available=True,
                category=cat,
            )

        url = reverse('store:search')
        resp_p1 = client.get(url, {'q': 'Bulon'})
        assert resp_p1.status_code == 200
        assert len(resp_p1.context['products']) == 30
        assert resp_p1.context['product_count'] == 35

        sq = SearchQuery.objects.get(query_text='bulon')
        assert sq.search_count == 1
        ps_count_after_p1 = ProductSearch.objects.count()
        assert ps_count_after_p1 == 8

        # Página 2: entrega los 5 restantes sin inflar métricas
        resp_p2 = client.get(url, {'q': 'Bulon', 'page': '2'})
        assert resp_p2.status_code == 200
        assert len(resp_p2.context['products']) == 5
        content_p2 = resp_p2.content.decode('utf-8')
        assert 'rel="prev"' in content_p2
        assert content_p2.count('page=1') >= 1
        assert 'page=2&amp;page=1' not in content_p2

        sq.refresh_from_db()
        assert sq.search_count == 1
        assert ProductSearch.objects.count() == ps_count_after_p1

        # Página fuera de rango: no infla métricas
        resp_p999 = client.get(url, {'q': 'Bulon', 'page': '999'})
        assert resp_p999.status_code == 200
        sq.refresh_from_db()
        assert sq.search_count == 1

    def test_search_view_sort_by_preserves_q_and_avoids_double_count(self, client, catalog_setup):
        url = reverse('store:search')
        resp = client.get(url, {'q': 'Bulonería', 'sort_by': 'price_asc'})
        assert resp.status_code == 200

        prices = [p.price for p in resp.context['products']]
        assert prices == [Decimal('250.00'), Decimal('450.00')]
        content = resp.content.decode('utf-8')
        assert '<input type="hidden" name="q" value="Bulonería">' in content
        assert SearchQuery.objects.count() == 0

    def test_get_paginated_products_uses_sql_count_and_limit(
        self, catalog_setup, django_assert_num_queries
    ):
        cat = catalog_setup['category']
        for i in range(3):
            Product.objects.create(
                name=f'Bulon SQL {i}',
                slug=f'bulon-sql-{i}',
                code=f'BUL-SQL-{i}',
                price=Decimal('150.00'),
                stock=5,
                is_available=True,
                category=cat,
            )

        qs = Product.objects.filter(is_available=True).order_by('id')
        with django_assert_num_queries(2):
            paged, total = ProductService.get_paginated_products(qs, page=1, per_page=2)
            items = list(paged)

        assert total == 5
        assert len(items) == 2

    def test_query_with_page_preserves_multivalue_and_encodes_fractions(self):
        qd = QueryDict('q=1/4 x 2&tags=inoxidable&tags=oferta&page=3')
        encoded = query_with_page(qd, 2)

        assert 'page=2' in encoded
        assert 'page=3' not in encoded
        assert 'tags=inoxidable' in encoded
        assert 'tags=oferta' in encoded
        assert 'q=1%2F4+x+2' in encoded


class TestSearchTelemetryRateLimit:
    """Pruebas de rate-limiting Redis anti-flood (SEC-SQ-001) y privacidad."""

    def test_extract_telemetry_client_ip_uses_rightmost_xff_hop(self, rf):
        req = rf.get(
            '/store/search/',
            HTTP_X_FORWARDED_FOR='1.1.1.1, 203.0.113.50',
            REMOTE_ADDR='127.0.0.1',
        )
        assert SearchService.extract_telemetry_client_ip(req) == '203.0.113.50'

    def test_rate_limit_tier1_blocks_excess_writes_and_protects_product_search(
        self, client, catalog_setup, settings
    ):
        settings.SEARCH_TELEMETRY_MAX_WRITES_PER_MIN = 3
        url = reverse('store:search')

        for _ in range(5):
            resp = client.get(url, {'q': 'Bulonería'}, REMOTE_ADDR='203.0.113.10')
            assert resp.status_code == 200

        sq = SearchQuery.objects.get(query_text='bulonería')
        assert sq.search_count == 3
        total_ps = sum(ProductSearch.objects.values_list('search_count', flat=True))
        assert total_ps == 6  # 3 búsquedas válidas × 2 productos

        # Otra IP distinta sí puede registrar normalmente
        resp_other = client.get(url, {'q': 'Bulonería'}, REMOTE_ADDR='203.0.113.11')
        assert resp_other.status_code == 200
        sq.refresh_from_db()
        assert sq.search_count == 4

    def test_rate_limit_tier2_blocks_new_terms_but_allows_existing_terms(self, settings, db):
        settings.SEARCH_TELEMETRY_MAX_NEW_TERMS_PER_10M = 2
        settings.SEARCH_TELEMETRY_MAX_WRITES_PER_MIN = 20

        assert SearchService.record_search_query('termino nuevo uno', 0, client_ip='203.0.113.20') is True
        assert SearchService.record_search_query('termino nuevo dos', 0, client_ip='203.0.113.20') is True
        # El tercer término nuevo de la misma IP se descarta
        assert SearchService.record_search_query('termino nuevo tres', 0, client_ip='203.0.113.20') is False
        assert SearchQuery.objects.count() == 2

        # Un término ya existente sigue actualizando mientras no supere Nivel 1
        assert SearchService.record_search_query('termino nuevo uno', 0, client_ip='203.0.113.20') is True
        assert SearchQuery.objects.get(query_text='termino nuevo uno').search_count == 2

    def test_global_circuit_breaker_blocks_multi_ip_new_term_flood(self, settings, db):
        settings.SEARCH_TELEMETRY_GLOBAL_MAX_NEW_TERMS_PER_10M = 3
        settings.SEARCH_TELEMETRY_MAX_NEW_TERMS_PER_10M = 10

        assert SearchService.record_search_query('termino global 1', 0, client_ip='203.0.113.31') is True
        assert SearchService.record_search_query('termino global 2', 0, client_ip='203.0.113.32') is True
        assert SearchService.record_search_query('termino global 3', 0, client_ip='203.0.113.33') is True
        assert SearchService.record_search_query('termino global 4', 0, client_ip='203.0.113.34') is False
        assert SearchQuery.objects.count() == 3

    def test_cache_keys_never_store_raw_client_ip(self, db):
        raw_ip = '203.0.113.99'
        SearchService.record_search_query('tuerca autofrenante', 0, client_ip=raw_ip)
        keys = list(getattr(cache, '_cache', {}).keys())
        assert len(keys) >= 1
        assert all(raw_ip not in str(k) for k in keys)

    def test_cache_failure_fails_closed_for_writes_and_open_for_store(self, client, db):
        url = reverse('store:search')
        with patch('store.services.cache.incr', side_effect=ConnectionError('redis down')):
            resp = client.get(url, {'q': 'herramienta electrica'}, REMOTE_ADDR='203.0.113.44')

        assert resp.status_code == 200
        assert SearchQuery.objects.count() == 0


class TestSearchQueryMigrationBackfill:
    """Prueba directa de la función de backfill de migración 0026."""

    def test_backfill_migration_0026_migrates_legacy_unmatched_records(self, db):
        mig_module = importlib.import_module('store.migrations.0026_backfill_searchquery_daily')
        legacy_sq = SearchQuery.objects.create(
            query_text='amoladora legacy',
            search_count=7,
            matched_count=0,
            unmatched_count=0,
            last_results_count=0,
        )

        mig_module.backfill_search_queries(apps, None)

        legacy_sq.refresh_from_db()
        assert legacy_sq.unmatched_count == 7
        assert legacy_sq.last_results_count == 0
        daily = SearchQueryDaily.objects.get(search_query=legacy_sq)
        assert daily.unmatched_count == 7
        assert daily.matched_count == 0


class TestSearchQueryAppSecHardening:
    """Pruebas adversariales de seguridad (XSS, fórmula Excel, CRLF, XFF, RO y PII)."""

    def test_admin_escapes_xss_payload_in_changelist_and_change_view(self, staff_viewer_client):
        # Arrange
        payload = '<script>alert(1)</script>'
        SearchService.record_search_query(payload, results_count=0)
        sq = SearchQuery.objects.get(query_text=payload)

        # Act
        changelist_resp = staff_viewer_client.get(reverse('admin:store_searchquery_changelist'))
        change_resp = staff_viewer_client.get(reverse('admin:store_searchquery_change', args=[sq.pk]))

        # Assert
        assert changelist_resp.status_code == 200
        assert change_resp.status_code == 200
        assert b'<script>alert(1)</script>' not in changelist_resp.content
        assert b'<script>alert(1)</script>' not in change_resp.content
        assert b'&lt;script&gt;alert(1)&lt;/script&gt;' in changelist_resp.content
        assert b'&lt;script&gt;alert(1)&lt;/script&gt;' in change_resp.content

    def test_admin_export_neutralizes_formula_injection_in_summary_search_filter(self, staff_viewer_client):
        # Arrange
        export_url = reverse('admin:store_searchquery_export_excel')

        # Act
        response = staff_viewer_client.get(export_url, {'q': '=1+1'})

        # Assert
        assert response.status_code == 200
        workbook = openpyxl.load_workbook(io.BytesIO(b''.join(response.streaming_content)))
        summary_ws = workbook['Resumen']
        filter_cell = None
        for row in summary_ws.iter_rows(min_row=1, max_col=2):
            if row[0].value == 'Filtro de texto':
                filter_cell = row[1]
                break
        assert filter_cell is not None
        assert filter_cell.data_type == 's'
        assert filter_cell.value == '=1+1'

    def test_admin_export_prevents_header_injection_via_period_param(self, staff_viewer_client):
        # Arrange
        export_url = reverse('admin:store_searchquery_export_excel')

        # Act
        response = staff_viewer_client.get(export_url, {'period': '90\r\nX-Injected: evil'})

        # Assert
        assert response.status_code == 200
        assert 'X-Injected' not in response.headers
        assert 'ranking_busquedas_bulonera_90d_' in response.headers.get('Content-Disposition', '')

    def test_xff_spoofing_first_hop_cannot_bypass_rate_limit(self, catalog_setup, settings):
        # Arrange
        settings.SEARCH_TELEMETRY_MAX_WRITES_PER_MIN = 3
        search_url = reverse('store:search')
        client = Client()
        browser_ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0'

        # Act
        for hop in range(1, 6):
            response = client.get(
                search_url,
                {'q': 'bulon'},
                HTTP_USER_AGENT=browser_ua,
                HTTP_X_FORWARDED_FOR=f'{hop}.{hop}.{hop}.{hop}, 203.0.113.77',
            )
            assert response.status_code == 200

        # Assert
        sq = SearchQuery.objects.get(query_text='bulon')
        assert sq.search_count == 3

    def test_admin_readonly_post_cannot_mutate_search_query(self, staff_viewer_client):
        # Arrange
        sq = SearchQuery.objects.create(
            query_text='tuerca m8',
            search_count=4,
            matched_count=4,
            unmatched_count=0,
            last_results_count=2,
        )
        change_url = reverse('admin:store_searchquery_change', args=[sq.pk])

        # Act
        staff_viewer_client.post(change_url, {'query_text': 'hacked', 'search_count': 999})

        # Assert
        sq.refresh_from_db()
        assert sq.query_text == 'tuerca m8'
        assert sq.search_count == 4

    def test_logs_never_leak_raw_query_or_client_ip(self, db, caplog):
        # Arrange
        import logging

        secret_query = 'termino_confidencial_xyz'
        secret_ip = '203.0.113.88'

        # Act
        with caplog.at_level(logging.INFO, logger='store.services'):
            SearchService.record_search_query(secret_query, 0, client_ip=secret_ip)
            with patch.object(SearchQuery.objects, 'get_or_create', side_effect=RuntimeError('db down')):
                SearchService.record_search_query(secret_query, 0, client_ip=secret_ip)

        # Assert
        assert secret_query not in caplog.text
        assert secret_ip not in caplog.text


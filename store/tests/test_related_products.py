"""
Tests unitarios y de integración para el motor de productos relacionados (Fase 1).
"""
import pytest
from django.core.cache import cache

from category.models import Category, SubCategory
from store.models import Product
from store.relation_utils import normalize_thread_format, parse_diameter_and_pitch
from store.services import RelatedProductService


@pytest.fixture(autouse=True)
def _clear_cache_around_tests():
    """Garantiza aislamiento de Redis entre cada prueba de relacionados."""
    cache.clear()
    yield
    cache.clear()


class TestTechnicalAttributeNormalization:
    """Pruebas unitarias de los normalizadores calibrados contra los patrones reales del catálogo."""

    @pytest.mark.parametrize(
        'raw_input, expected_diam, expected_pitch',
        [
            ('6 x P 1.0', '6', '1'),
            ('10 x P 1.50', '10', '1.5'),
            ('10 x P 1.5', '10', '1.5'),
            ('10 x 1.50', '10', '1.5'),
            ('12 x P 1.25', '12', '1.25'),
            ('12 x P 1.50', '12', '1.5'),
            ('14 x P 2.00', '14', '2'),
            ('1/2 (12.7mm)', '1/2', ''),
            ('1/2', '1/2', ''),
            ('1/2 x 12H', '1/2', '12h'),
            ('1/2 x 13H', '1/2', '13h'),
            ('1.1/8 (28.575mm)', '1.1/8', ''),
            ('1-1/2"', '1.1/2', ''),
            ('1 1/2', '1.1/2', ''),
            ('M 6', '6', ''),
            ('M6', '6', ''),
            ('6mm', '6', ''),
            ('8 (4.2)', '8', ''),
            ('8 x 12', '8x12', ''),
            ('5 x 8', '5x8', ''),
            ('4 ', '4', ''),
            ('', '', ''),
        ],
    )
    def test_parse_diameter_and_pitch_real_patterns(self, raw_input, expected_diam, expected_pitch):
        diam, pitch = parse_diameter_and_pitch(raw_input)
        assert diam == expected_diam
        assert pitch == expected_pitch

    @pytest.mark.parametrize(
        'raw_thread, expected_family, expected_pitch',
        [
            ('USS / UNC(rosca gruesa)', 'unc', ''),
            ('UNC/BSW', 'unc', ''),
            ('USS (rosca gruesa)', 'unc', ''),
            ('UNF (rosca fina)', 'unf', ''),
            ('Pulgada', 'inch', ''),
            ('MA (rosca gruesa)', 'ma', ''),
            ('MB (rosca fina)', 'mb', ''),
            ('Milimétrica', 'metric', ''),
            ('P 1.0', '', '1'),
            ('1.25', '', '1.25'),
            ('13H', '', '13h'),
            ('', '', ''),
        ],
    )
    def test_normalize_thread_format_real_patterns(self, raw_thread, expected_family, expected_pitch):
        family, pitch = normalize_thread_format(raw_thread)
        assert family == expected_family
        assert pitch == expected_pitch


@pytest.mark.django_db
class TestRelatedProductService:
    """Pruebas de integración para Opción C, Opción B, variedad, caché y signals."""

    @pytest.fixture
    def catalog_setup(self):
        cat_bul = Category.objects.create(category_name='Bulonería', slug='buloneria')
        cat_fer = Category.objects.create(category_name='Ferretería', slug='ferreteria')
        sub_bulon = SubCategory.objects.create(subcategory_name='bulon milimetrico', slug='bulon-milimetrico', category=cat_bul)
        sub_tuerca = SubCategory.objects.create(subcategory_name='Tuercas Hexagonales', slug='tuercas-hexagonales', category=cat_bul)
        sub_arandela = SubCategory.objects.create(subcategory_name='Arandelas', slug='arandelas', category=cat_bul)
        sub_tirafondo = SubCategory.objects.create(subcategory_name='Tirafondos', slug='tirafondos', category=cat_bul)
        sub_tarugo = SubCategory.objects.create(subcategory_name='Tarugos Nylon', slug='tarugos-nylon', category=cat_fer)
        sub_mecha = SubCategory.objects.create(subcategory_name='Mechas Widia', slug='mechas-widia', category=cat_fer)
        sub_disco = SubCategory.objects.create(subcategory_name='Discos de Corte', slug='discos-de-corte', category=cat_fer)
        return {
            'cat_bul': cat_bul,
            'cat_fer': cat_fer,
            'sub_bulon': sub_bulon,
            'sub_tuerca': sub_tuerca,
            'sub_arandela': sub_arandela,
            'sub_tirafondo': sub_tirafondo,
            'sub_tarugo': sub_tarugo,
            'sub_mecha': sub_mecha,
            'sub_disco': sub_disco,
        }

    def test_option_c_bulon_m6_recommends_matching_nut_and_washer_without_thread(self, catalog_setup):
        cat_bul = catalog_setup['cat_bul']
        bulon = Product.objects.create(
            code='01200106100',
            name='Bulón Hexagonal G8.8 6 x P 1.0 x 100',
            diameter='6 x P 1.0',
            length='100',
            thread_formats='MA (rosca gruesa)',
            material='Acero',
            price=250.0,
            stock=50,
            category=cat_bul,
            diameter_relation='6 x P 1.0',
            thread_formats_relation='MA (rosca gruesa)',
        )
        bulon.subcategories.add(catalog_setup['sub_bulon'])
        bulon.related_subcategories.add(catalog_setup['sub_tuerca'], catalog_setup['sub_arandela'])

        tuerca_m6 = Product.objects.create(
            code='T-M6',
            name='Tuerca Hexagonal 6 x P 1.0',
            diameter='6 x P 1.0',
            thread_formats='MA (rosca gruesa)',
            material='Acero',
            price=40.0,
            stock=100,
            category=cat_bul,
        )
        tuerca_m6.subcategories.add(catalog_setup['sub_tuerca'])

        tuerca_m10 = Product.objects.create(
            code='T-M10',
            name='Tuerca Hexagonal 10 x P 1.50',
            diameter='10 x P 1.50',
            thread_formats='MA (rosca gruesa)',
            price=90.0,
            stock=100,
            category=cat_bul,
        )
        tuerca_m10.subcategories.add(catalog_setup['sub_tuerca'])

        arandela_m6 = Product.objects.create(
            code='A-M6',
            name='Arandela Plana M 6',
            diameter='M 6',
            thread_formats=None,
            price=15.0,
            stock=200,
            category=cat_bul,
        )
        arandela_m6.subcategories.add(catalog_setup['sub_arandela'])

        arandela_m8 = Product.objects.create(
            code='A-M8',
            name='Arandela Plana 8mm',
            diameter='8mm',
            thread_formats=None,
            price=20.0,
            stock=200,
            category=cat_bul,
        )
        arandela_m8.subcategories.add(catalog_setup['sub_arandela'])

        results = RelatedProductService.get_related_products(bulon, limit=6)
        returned_codes = [item['product'].code for item in results]

        assert 'T-M6' in returned_codes
        assert 'A-M6' in returned_codes
        assert 'T-M10' not in returned_codes
        assert 'A-M8' not in returned_codes

        badges_by_code = {item['product'].code: item['badge'] for item in results}
        assert badges_by_code['T-M6'].startswith('Compatible 6')
        assert badges_by_code['A-M6'] == 'Medida 6'

    def test_option_c_distinguishes_fine_thread_pitch_12_125_vs_12_150(self, catalog_setup):
        cat_bul = catalog_setup['cat_bul']
        bulon = Product.objects.create(
            code='B-12-125',
            name='Bulón 12 x P 1.25 x 50',
            diameter='12 x P 1.25',
            thread_formats='MB (rosca fina)',
            price=300.0,
            stock=10,
            category=cat_bul,
            diameter_relation='12 x P 1.25',
            thread_formats_relation='MB (rosca fina)',
        )
        bulon.related_subcategories.add(catalog_setup['sub_tuerca'])

        tuerca_125 = Product.objects.create(
            code='T-12-125',
            name='Tuerca 12 x P 1.25',
            diameter='12 x P 1.25',
            thread_formats='MB (rosca fina)',
            price=80.0,
            stock=10,
            category=cat_bul,
        )
        tuerca_125.subcategories.add(catalog_setup['sub_tuerca'])

        tuerca_150 = Product.objects.create(
            code='T-12-150',
            name='Tuerca 12 x P 1.50',
            diameter='12 x P 1.50',
            thread_formats='MB (rosca fina)',
            price=85.0,
            stock=10,
            category=cat_bul,
        )
        tuerca_150.subcategories.add(catalog_setup['sub_tuerca'])

        results = RelatedProductService.get_related_products(bulon, limit=6)
        assert [item['product'].code for item in results] == ['T-12-125']

    def test_option_c_supports_multiple_diameters_and_never_degrades_on_zero_stock(self, catalog_setup):
        cat_bul = catalog_setup['cat_bul']
        cat_fer = catalog_setup['cat_fer']
        tirafondo = Product.objects.create(
            code='TIR-06',
            name='Tirafondo 6 x 50',
            diameter='6',
            length='50',
            price=50.0,
            stock=30,
            category=cat_bul,
            diameter_relation='8, 10',
        )
        tirafondo.related_subcategories.add(catalog_setup['sub_tarugo'], catalog_setup['sub_mecha'])

        t8 = Product.objects.create(
            code='TAR-08', name='Tarugo Nylon 8', diameter='8', price=10.0, stock=50, category=cat_fer
        )
        t8.subcategories.add(catalog_setup['sub_tarugo'])

        t10 = Product.objects.create(
            code='TAR-10', name='Tarugo Nylon 10', diameter='10', price=14.0, stock=50, category=cat_fer
        )
        t10.subcategories.add(catalog_setup['sub_tarugo'])

        # Mecha de 16mm existe con stock, pero NO hay mecha de 8 ni 10 -> debe omitir Mechas Widia (NO Opción B)
        mecha_16 = Product.objects.create(
            code='MEC-16', name='Mecha Widia 16mm', diameter='16mm', price=900.0, stock=5, category=cat_fer
        )
        mecha_16.subcategories.add(catalog_setup['sub_mecha'])

        results = RelatedProductService.get_related_products(tirafondo, limit=6)
        codes = [item['product'].code for item in results]
        assert set(codes) == {'TAR-08', 'TAR-10'}
        assert 'MEC-16' not in codes

    def test_option_b_when_relation_fields_are_empty(self, catalog_setup):
        cat_fer = catalog_setup['cat_fer']
        taladro = Product.objects.create(
            code='TAL-18V',
            name='Taladro Percutor 18V',
            price=180000.0,
            stock=5,
            category=cat_fer,
            diameter_relation='',
            thread_formats_relation='',
        )
        taladro.related_subcategories.add(catalog_setup['sub_mecha'], catalog_setup['sub_disco'])

        m1 = Product.objects.create(
            code='MEC-08', name='Mecha Widia 8mm', diameter='8mm', price=500.0, stock=15, sold_count=20, category=cat_fer
        )
        m1.subcategories.add(catalog_setup['sub_mecha'])
        d1 = Product.objects.create(
            code='DIS-115', name='Disco Corte 115mm', price=800.0, stock=25, sold_count=40, category=cat_fer
        )
        d1.subcategories.add(catalog_setup['sub_disco'])

        results = RelatedProductService.get_related_products(taladro, limit=6)
        assert len(results) == 2
        assert {item['match_level'] for item in results} == {'subcategory'}
        assert {item['product'].code for item in results} == {'MEC-08', 'DIS-115'}

    def test_cache_revalidates_stock_on_hit_and_invalidates_via_signal(self, catalog_setup):
        cat_fer = catalog_setup['cat_fer']
        origen = Product.objects.create(
            code='ORG-01', name='Amoladora', price=100000.0, stock=3, category=cat_fer
        )
        origen.related_subcategories.add(catalog_setup['sub_disco'])

        disco1 = Product.objects.create(
            code='D-01', name='Disco 1', price=500.0, stock=10, sold_count=5, category=cat_fer
        )
        disco1.subcategories.add(catalog_setup['sub_disco'])
        disco2 = Product.objects.create(
            code='D-02', name='Disco 2', price=600.0, stock=10, sold_count=1, category=cat_fer
        )
        disco2.subcategories.add(catalog_setup['sub_disco'])

        first = RelatedProductService.get_related_products(origen, limit=6)
        assert [i['product'].code for i in first] == ['D-01', 'D-02']

        # Simula baja de stock masiva sin disparar signal en disco1 -> cache hit debe filtrarlo
        Product.objects.filter(pk=disco1.pk).update(stock=0)
        second = RelatedProductService.get_related_products(origen, limit=6)
        assert [i['product'].code for i in second] == ['D-02']

        # Cambiar related_subcategories debe invalidar la clave Redis vía signal m2m_changed
        cache_key = f"{RelatedProductService.CACHE_KEY_PREFIX}:{origen.pk}"
        assert cache.get(cache_key) is not None
        origen.related_subcategories.clear()
        assert cache.get(cache_key) is None

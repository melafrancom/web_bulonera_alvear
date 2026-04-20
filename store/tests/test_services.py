"""
Store App Services Tests

Tests reales para ProductService, SearchService, ReviewService, FAQService, CarouselService.
"""
import pytest
from django.test import TestCase
from store.models import Product, ReviewRating, FAQ, FAQCategory, CarouselImage
from store.services import (
    ProductService, SearchService, ReviewService, FAQService, CarouselService
)
from category.models import Category, SubCategory


@pytest.mark.django_db
class TestProductService:
    """Tests para ProductService"""

    def test_get_all_products_available(self, category):
        """Obtiene solo productos disponibles"""
        # Crear productos
        p1 = Product.objects.create(
            code='PROD-001',
            name='Producto 1',
            slug='producto-1',
            price=10.0,
            stock=100,
            category=category,
            is_available=True
        )
        p2 = Product.objects.create(
            code='PROD-002',
            name='Producto 2',
            slug='producto-2',
            price=20.0,
            stock=50,
            category=category,
            is_available=False
        )
        
        products = ProductService.get_all_products(is_available=True)
        assert products.count() == 1
        assert p1 in products
        assert p2 not in products

    def test_get_all_products_unavailable(self, category):
        """Obtiene solo productos no disponibles"""
        Product.objects.create(
            code='PROD-001',
            name='Producto Disponible',
            slug='producto-disponible',
            price=10.0,
            stock=100,
            category=category,
            is_available=True
        )
        p_unavailable = Product.objects.create(
            code='PROD-002',
            name='Producto No Disponible',
            slug='producto-no-disponible',
            price=20.0,
            stock=0,
            category=category,
            is_available=False
        )
        
        products = ProductService.get_all_products(is_available=False)
        assert p_unavailable in products

    def test_get_product_by_slug_success(self, product):
        """Obtiene producto por slug correctamente"""
        result = ProductService.get_product_by_slug(product.slug)
        assert result is not None
        assert result == product
        assert result.name == product.name

    def test_get_product_by_slug_not_found(self):
        """Retorna None cuando no existe el producto"""
        result = ProductService.get_product_by_slug('slug-inexistente')
        assert result is None

    def test_get_product_by_slug_with_category(self, product):
        """Obtiene producto por slug y categoría"""
        result = ProductService.get_product_by_slug(
            product.slug,
            category_slug=product.category.slug
        )
        assert result == product

    def test_filter_products_by_price(self, category):
        """Filtra productos por rango de precio"""
        p1 = Product.objects.create(
            code='CHEAP',
            name='Barato',
            slug='barato',
            price=5.0,
            stock=10,
            category=category
        )
        p2 = Product.objects.create(
            code='EXPENSIVE',
            name='Caro',
            slug='caro',
            price=100.0,
            stock=10,
            category=category
        )
        
        products = Product.objects.all()
        filtered = ProductService.filter_products(
            products,
            min_price=10.0,
            max_price=50.0
        )
        
        assert p1 not in filtered
        assert p2 not in filtered

    def test_filter_products_by_brand(self, category):
        """Filtra productos por marca"""
        p1 = Product.objects.create(
            code='BRAND-A',
            name='Producto Marca A',
            slug='producto-marca-a',
            price=10.0,
            stock=10,
            category=category,
            brand='Marca A'
        )
        p2 = Product.objects.create(
            code='BRAND-B',
            name='Producto Marca B',
            slug='producto-marca-b',
            price=10.0,
            stock=10,
            category=category,
            brand='Marca B'
        )
        
        products = Product.objects.all()
        filtered = ProductService.filter_products(products, brand='Marca A')
        
        assert p1 in filtered
        assert p2 not in filtered

    def test_filter_products_sort_by_price_asc(self, category):
        """Ordena productos por precio ascendente"""
        Product.objects.create(
            code='P1', name='P1', slug='p1',
            price=50.0, stock=10, category=category
        )
        Product.objects.create(
            code='P2', name='P2', slug='p2',
            price=10.0, stock=10, category=category
        )
        Product.objects.create(
            code='P3', name='P3', slug='p3',
            price=30.0, stock=10, category=category
        )
        
        products = Product.objects.all()
        filtered = ProductService.filter_products(products, sort_by='price_asc')
        filtered_list = list(filtered)
        
        assert filtered_list[0].price == 10.0
        assert filtered_list[1].price == 30.0
        assert filtered_list[2].price == 50.0

    def test_get_available_brands(self, category):
        """Obtiene marcas únicas disponibles"""
        Product.objects.create(
            code='A1', name='A1', slug='a1',
            price=10.0, stock=10, category=category, brand='Marca 1'
        )
        Product.objects.create(
            code='A2', name='A2', slug='a2',
            price=10.0, stock=10, category=category, brand='Marca 2'
        )
        Product.objects.create(
            code='A3', name='A3', slug='a3',
            price=10.0, stock=10, category=category  # sin marca
        )
        
        brands = ProductService.get_available_brands()
        assert 'Marca 1' in brands
        assert 'Marca 2' in brands
        assert 'sin_marca' in brands

    def test_get_paginated_products(self, category):
        """Pagina productos correctamente"""
        for i in range(35):
            Product.objects.create(
                code=f'P{i}',
                name=f'Producto {i}',
                slug=f'producto-{i}',
                price=10.0,
                stock=10,
                category=category
            )
        
        products = Product.objects.all()
        paged, total = ProductService.get_paginated_products(products, page=1, per_page=30)
        
        assert total == 35
        assert len(paged) == 30
        
        paged2, _ = ProductService.get_paginated_products(products, page=2, per_page=30)
        assert len(paged2) == 5


@pytest.mark.django_db
class TestSearchService:
    """Tests para SearchService"""

    def test_search_products_by_keyword(self, category):
        """Busca productos por palabra clave"""
        p1 = Product.objects.create(
            code='TORNILLO',
            name='Tornillo de Acero',
            slug='tornillo-acero',
            price=10.0,
            stock=100,
            category=category,
            is_available=True
        )
        p2 = Product.objects.create(
            code='TUERCA',
            name='Tuerca de Latón',
            slug='tuerca-laton',
            price=5.0,
            stock=50,
            category=category,
            is_available=True
        )
        
        results = SearchService.search_products('Tornillo')
        assert p1 in results
        assert p2 not in results

    def test_search_products_empty_keyword(self, product):
        """Sin keyword devuelve todos los disponibles"""
        results = SearchService.search_products('')
        assert product in results

    def test_search_products_by_description(self, category):
        """Busca por descripción del producto"""
        p = Product.objects.create(
            code='DESC-TEST',
            name='Producto Normal',
            slug='producto-normal',
            price=10.0,
            stock=10,
            category=category,
            description='Este es un tornillo de acero inoxidable',
            is_available=True
        )
        
        results = SearchService.search_products('inoxidable')
        assert p in results

    def test_search_products_unavailable_excluded(self, category):
        """Excluye productos no disponibles de la búsqueda"""
        Product.objects.create(
            code='NOT-AVAIL',
            name='Hornillas Inoxidables',
            slug='hornillas-inox',
            price=10.0,
            stock=0,
            category=category,
            is_available=False
        )
        
        results = SearchService.search_products('Inoxidables')
        assert results.count() == 0


@pytest.mark.django_db
class TestReviewService:
    """Tests para ReviewService"""

    def test_create_review(self, user, product):
        """Crea una review correctamente"""
        review = ReviewService.create_review(
            user_id=user.id,
            product_id=product.id,
            subject='Excelente producto',
            review='Me encantó',
            rating=5.0,
            ip='127.0.0.1'
        )
        
        assert review.subject == 'Excelente producto'
        assert review.rating == 5.0
        assert review.user == user
        assert review.product == product

    def test_get_product_reviews(self, user, product):
        """Obtiene reviews de un producto"""
        ReviewService.create_review(
            user_id=user.id,
            product_id=product.id,
            subject='Review 1',
            review='Bueno',
            rating=4.0,
            ip='127.0.0.1'
        )
        ReviewService.create_review(
            user_id=user.id,
            product_id=product.id,
            subject='Review 2',
            review='Muy bueno',
            rating=5.0,
            ip='127.0.0.1'
        )
        
        reviews = ReviewService.get_product_reviews(product.id)
        assert reviews.count() == 2

    def test_get_user_review(self, user, product):
        """Obtiene review de un usuario para un producto"""
        created_review = ReviewService.create_review(
            user_id=user.id,
            product_id=product.id,
            subject='Mi review',
            review='Contenido',
            rating=3.0,
            ip='127.0.0.1'
        )
        
        review = ReviewService.get_user_review(user.id, product.id)
        assert review is not None
        assert review == created_review

    def test_update_review(self, user, product):
        """Actualiza una review existente"""
        review = ReviewService.create_review(
            user_id=user.id,
            product_id=product.id,
            subject='Original',
            review='Contenido original',
            rating=2.0,
            ip='127.0.0.1'
        )
        
        updated = ReviewService.update_review(
            review,
            subject='Actualizado',
            rating=5.0
        )
        
        assert updated.subject == 'Actualizado'
        assert updated.rating == 5.0


@pytest.mark.django_db
class TestFAQService:
    """Tests para FAQService"""

    def test_get_general_faqs(self):
        """Obtiene FAQs generales"""
        category = FAQCategory.objects.create(name='General', order=1)
        FAQ.objects.create(
            category=category,
            question='¿Cómo compro?',
            answer='Haz clic en agregar al carrito',
            order=1,
            is_active=True
        )
        
        faqs = FAQService.get_general_faqs()
        assert faqs is not None

    def test_get_product_faqs(self, product):
        """Obtiene FAQs relacionadas a un producto"""
        subcat = SubCategory.objects.create(
            subcategory_name='Tornillos',
            slug='tornillos',
            category=product.category
        )
        product.subcategories.add(subcat)
        
        category = FAQCategory.objects.create(name='Productos', order=1)
        FAQ.objects.create(
            category=category,
            subcategory=subcat,
            question='¿Tamaño?',
            answer='3mm',
            order=1,
            is_active=True
        )
        
        faqs = FAQService.get_product_faqs(product)
        assert faqs.count() >= 1


@pytest.mark.django_db
class TestCarouselService:
    """Tests para CarouselService"""

    def test_get_active_carousel_images(self):
        """Obtiene imágenes activas del carrusel"""
        CarouselImage.objects.create(
            title='Carousel 1',
            position=1,
            is_active=True
        )
        CarouselImage.objects.create(
            title='Carousel 2',
            position=2,
            is_active=False
        )
        
        images = CarouselService.get_active_carousel_images()
        assert images.count() == 1
        assert images[0].title == 'Carousel 1'

    def test_carousel_images_ordered_by_position(self):
        """Carrusel ordena por posición"""
        CarouselImage.objects.create(title='C3', position=3, is_active=True)
        CarouselImage.objects.create(title='C1', position=1, is_active=True)
        CarouselImage.objects.create(title='C2', position=2, is_active=True)
        
        images = CarouselService.get_active_carousel_images()
        positions = [img.position for img in images]
        
        assert positions == [1, 2, 3]


@pytest.mark.django_db
class TestProductImportRegression:
    """Tests de regresión para importación de productos (Fix Bug #1, #2, #3)"""

    def test_parse_file_code_mantiene_ceros_a_la_izquierda(self):
        """El parser no debe convertir '00100200020' en '100200020' o '100200020.0'"""
        import pandas as pd
        from io import BytesIO
        
        # Crear DataFrame con código que tiene ceros a la izquierda
        data = [{'code': '00100200020', 'price': '100.0', 'category': 'Test'}]
        df = pd.DataFrame(data)
        
        # Guardar como Excel
        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)
        buffer.name = 'test.xlsx'
        
        # Parsear con el método corregido
        result = ProductService._parse_file(buffer)
        
        # Verificar que el código mantiene los ceros a la izquierda
        assert result[0]['code'] == '00100200020'
        assert not result[0]['code'].endswith('.0')

    def test_parse_file_header_mayusculas_es_normalizado(self):
        """El parser debe funcionar aunque el Excel tenga 'Code' en lugar de 'code'"""
        import pandas as pd
        from io import BytesIO
        
        # DataFrame con columna 'Code' (mayúscula) - simula el Excel real
        df = pd.DataFrame([{'Code': '12345', 'Price': '100.0', 'Category': 'Test'}])
        
        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)
        buffer.name = 'test.xlsx'
        
        result = ProductService._parse_file(buffer)
        
        # Verificar que los headers fueron normalizados a lowercase
        assert 'code' in result[0]
        assert 'price' in result[0]
        assert 'category' in result[0]
        assert result[0]['code'] == '12345'

    def test_sanitize_price_formato_argentino_con_simbolo(self):
        """$7.161,61 debe retornar 7161.61"""
        result = ProductService._sanitize_price('$7.161,61')
        assert result == 7161.61

    def test_sanitize_price_formato_europeo(self):
        """7.161,61 debe retornar 7161.61"""
        result = ProductService._sanitize_price('7.161,61')
        assert result == 7161.61

    def test_sanitize_price_formato_americano(self):
        """7,161.61 debe retornar 7161.61"""
        result = ProductService._sanitize_price('7,161.61')
        assert result == 7161.61

    def test_sanitize_price_float_directo(self):
        """Si Pandas parsea el número, debe aceptarlo sin string processing"""
        result = ProductService._sanitize_price(7161.61)
        assert result == 7161.61

    def test_sanitize_price_integer(self):
        """Un entero debe convertirse a float correctamente"""
        result = ProductService._sanitize_price(1000)
        assert result == 1000.0

    def test_sanitize_price_con_espacio_no_breaking(self):
        """$ 7.161,61 con non-breaking space debe retornar 7161.61"""
        result = ProductService._sanitize_price('$\xa07.161,61')
        assert result == 7161.61

    def test_sanitize_price_rechaza_negativo(self):
        """Debe rechazar precios negativos"""
        with pytest.raises(ValueError, match="negativo"):
            ProductService._sanitize_price(-100.0)

    def test_sanitize_price_rechaza_vacio(self):
        """Debe rechazar precios vacíos o None"""
        with pytest.raises(ValueError, match="vacío"):
            ProductService._sanitize_price(None)

    def test_import_actualiza_no_duplica_si_codigo_ya_existe(self, category):
        """Si el código ya existe, debe actualizar — no crear un segundo registro"""
        import pandas as pd
        from io import BytesIO
        
        # Crear producto inicial
        Product.objects.create(
            code='00101',
            name='Original',
            slug='original',
            price=50.0,
            stock=10,
            category=category
        )
        
        # Preparar datos de importación con el mismo código
        data = [{'code': '00101', 'name': 'Actualizado', 'price': '75.0',
                 'category': category.category_name, 'stock': '20'}]
        df = pd.DataFrame(data)
        
        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)
        buffer.name = 'test.xlsx'
        
        # Importar
        result = ProductService.import_from_file(buffer)
        
        # Verificar que se actualizó, no se creó
        assert result.created == 0
        assert result.updated == 1
        
        # CRÍTICO: solo debe existir UN producto con ese código
        assert Product.objects.filter(code='00101').count() == 1
        
        # Verificar que se actualizó el precio
        product = Product.objects.get(code='00101')
        assert product.price == 75.0
        assert product.name == 'Actualizado'
        assert product.stock == 20

    def test_parse_file_elimina_sufijo_punto_cero(self):
        """Si el código viene como '100200.0' debe limpiarse a '100200'"""
        import pandas as pd
        from io import BytesIO
        
        # Simular un Excel donde Pandas infirió el código como float
        # (esto ya no debería pasar con dtype=str, pero validamos la limpieza)
        data = [{'code': '100200.0', 'price': '50.0'}]
        df = pd.DataFrame(data)
        
        buffer = BytesIO()
        df.to_excel(buffer, index=False)
        buffer.seek(0)
        buffer.name = 'test.xlsx'
        
        result = ProductService._parse_file(buffer)
        
        # Verificar que el sufijo .0 fue eliminado
        assert result[0]['code'] == '100200'
        assert not result[0]['code'].endswith('.0')

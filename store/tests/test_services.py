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

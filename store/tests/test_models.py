import pytest
from django.test import TestCase
from store.models import Product, ReviewRating
from category.models import Category


@pytest.mark.django_db
class TestProductModel:
    """Tests del modelo Product."""

    def test_product_creation(self, product):
        """Verifica que se puede crear un producto correctamente."""
        assert product.code == 'SCREW-001'
        assert product.name == 'Tornillo Acero Inox 3mm'
        assert product.slug == 'tornillo-acero-inox-3mm'
        assert product.price == 10.50
        assert product.stock == 100
        assert product.is_available is True

    def test_product_str(self, product):
        """Verifica la representación en string del producto."""
        assert str(product) == product.name

    def test_product_absolute_url(self, product):
        """Verifica que el producto tiene una URL absoluta."""
        assert product.get_absolute_url() is not None

    def test_product_slug_unique(self, product):
        """Verifica que el slug es único."""
        with pytest.raises(Exception):  # IntegrityError
            Product.objects.create(
                code='SCREW-002',
                name='Otro Tornillo',
                slug=product.slug,  # Mismo slug
                price=5.0,
                stock=50,
                category=product.category
            )

    def test_product_available_filter(self, category):
        """Verifica el filtro de productos disponibles."""
        # Crear productos disponibles e indisponibles
        Product.objects.create(
            code='SCREW-AVAIL',
            name='Tornillo Disponible',
            slug='tornillo-disponible',
            price=10.0,
            stock=50,
            category=category,
            is_available=True
        )
        
        Product.objects.create(
            code='SCREW-UNAVAIL',
            name='Tornillo No Disponible',
            slug='tornillo-no-disponible',
            price=10.0,
            stock=0,
            category=category,
            is_available=False
        )
        
        available = Product.objects.filter(is_available=True)
        assert available.count() == 1
        assert available.first().name == 'Tornillo Disponible'


@pytest.mark.django_db
class TestReviewRatingModel:
    """Tests del modelo ReviewRating."""

    def test_review_creation(self, product, user):
        """Verifica que se puede crear una reseña."""
        review = ReviewRating.objects.create(
            product=product,
            user=user,
            subject='Excelente producto',
            review='Muy buena calidad',
            rating=5,
            ip='127.0.0.1'
        )
        assert review.product == product
        assert review.user == user
        assert review.rating == 5

    def test_review_rating_choices(self, product, user):
        """Verifica que el rating respeta las opciones válidas."""
        review = ReviewRating.objects.create(
            product=product,
            user=user,
            subject='Test',
            review='Test',
            rating=3,
            ip='127.0.0.1'
        )
        assert review.rating in [1, 2, 3, 4, 5]

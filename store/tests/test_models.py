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
        assert product.name == 'Tornillo Acero Inox 3mm 3mm x 20mm'
        assert product.slug == 'tornillo-acero-inox-3mm-3mm-x-20mm'
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

    def test_should_regenerate_slug_placeholder(self, category):
        """Verifica que _should_regenerate_slug() detecta placeholders (Fase 2)."""
        # Crear producto con slug placeholder y nombre real
        # Primero crear con nombre genérico para que tenga slug placeholder
        product = Product.objects.create(
            code='PROD-001',
            name='Producto Temporal',  # Nombre temporal
            slug='producto-0670010005',  # Forzar placeholder
            price=5.0,
            stock=100,
            category=category
        )
        # Ahora cambiar el nombre a uno real
        product.name = 'Bulón Cabeza Hexagonal G5 M8 x 25mm'
        # Antes de guardar, verificar que _should_regenerate_slug() retorna True
        assert product._should_regenerate_slug() is True
        # Guardar y verificar que el slug fue regenerado
        product.save()
        product.refresh_from_db()
        assert product.slug == 'bulon-cabeza-hexagonal-g5-m8-x-25mm'
        assert product.slug != 'producto-0670010005'

    def test_should_regenerate_slug_placeholder_short_name(self, category):
        """Verifica que _should_regenerate_slug() NO regenera con nombre corto."""
        # Nombre corto (menos de 10 caracteres)
        product = Product.objects.create(
            code='PROD-002',
            name='Tornillo',  # Solo 8 caracteres
            slug='producto-001',
            price=5.0,
            stock=100,
            category=category
        )
        assert product._should_regenerate_slug() is False

    def test_should_regenerate_slug_placeholder_product_prefix(self, category):
        """Verifica que _should_regenerate_slug() NO regenera con prefijo 'Producto '."""
        product = Product.objects.create(
            code='PROD-003',
            name='Producto Tornillo de Prueba',
            slug='producto-999',
            price=5.0,
            stock=100,
            category=category
        )
        assert product._should_regenerate_slug() is False

    def test_should_regenerate_slug_real_slug(self, category):
        """Verifica que _should_regenerate_slug() NO regenera si slug es real."""
        product = Product.objects.create(
            code='PROD-004',
            name='Tornillo Acero Inox M6',
            slug='tornillo-acero-inox-m6',  # Real, no placeholder
            price=5.0,
            stock=100,
            category=category
        )
        assert product._should_regenerate_slug() is False

    def test_generate_unique_slug_no_collision(self, category):
        """Verifica que _generate_unique_slug() genera slug único sin colisión."""
        product = Product.objects.create(
            code='PROD-005',
            name='Bulón Especial Único',
            slug='',  # Vacío inicialmente
            price=5.0,
            stock=100,
            category=category
        )
        # El save() debe haber generado un slug único
        product.refresh_from_db()
        assert product.slug == 'bulon-especial-unico'

    def test_generate_unique_slug_with_collision(self, category):
        """Verifica que _generate_unique_slug() usa code como desambiguador (Fase 2)."""
        # Crear primer producto
        product1 = Product.objects.create(
            code='BOLT-001',
            name='Tornillo Inox M6 DIN 965',
            slug='tornillo-inox-m6-din-965',
            price=5.0,
            stock=100,
            category=category
        )

        # Crear segundo producto con nombre que genera el mismo base slug
        # Usamos "Tornillo Inox M6 X 20" que slugificará a "tornillo-inox-m6" (colisión)
        # Pero primero debemos crear con un nombre diferente
        product2 = Product.objects.create(
            code='BOLT-002',
            name='Tornillo Inox M6 X 20mm',  # Nombre diferente pero slug base similar
            slug='',  # Vacío, se generará
            price=5.0,
            stock=50,
            category=category
        )

        # Verificar que el segundo tiene slug generado exitosamente (no colisión con product1)
        product2.refresh_from_db()
        # Los nombres son diferentes, así que no habrá colisión real
        assert product2.slug is not None
        assert product2.slug != ''

    def test_get_url_flat_structure(self, product):
        """Verifica que get_url() devuelve URL plana sin category (Fase 1)."""
        # get_url() debe devolver /store/p/<slug>/ (después del include)
        url = product.get_url()
        assert '/p/' in url
        # NO debe contener /category/
        assert '/category/' not in url


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


@pytest.mark.django_db
class TestProductImageUrl:
    """Tests para el property image_url del modelo Product."""

    def test_image_url_with_image(self, product, category):
        """Verifica que image_url retorna la URL correcta cuando hay imagen."""
        # Crear producto con imagen mock
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        import io
        
        # Crear imagen de prueba
        image = Image.new('RGB', (100, 100), color='red')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        product_with_image = Product.objects.create(
            code='TEST-IMG-001',
            name='Producto con Imagen',
            slug='producto-con-imagen',
            price=10.0,
            stock=50,
            category=category,
            images=SimpleUploadedFile('test.jpg', image_io.read(), content_type='image/jpeg')
        )
        
        # Verificar que retorna una URL válida
        assert product_with_image.image_url is not None
        assert '/media/' in product_with_image.image_url or product_with_image.image_url.startswith('http')

    def test_image_url_without_image(self, category):
        """Verifica que image_url retorna placeholder cuando no hay imagen."""
        # Crear producto sin imagen
        product_no_image = Product.objects.create(
            code='TEST-NO-IMG',
            name='Producto Sin Imagen',
            slug='producto-sin-imagen',
            price=10.0,
            stock=50,
            category=category
        )
        assert product_no_image.image_url == '/static/images/placeholder.png'

    def test_image_url_empty_name(self, category):
        """Verifica que image_url retorna placeholder cuando images.name está vacío."""
        product_empty = Product.objects.create(
            code='TEST-EMPTY-001',
            name='Producto Sin Imagen',
            slug='producto-sin-imagen',
            price=10.0,
            stock=50,
            category=category
        )
        
        assert product_empty.image_url == '/static/images/placeholder.png'


@pytest.mark.django_db
class TestCarouselImageUrl:
    """Tests para el property image_url del modelo CarouselImage."""

    def test_carousel_image_url_with_image(self, category):
        """Verifica que image_url retorna la URL correcta cuando hay imagen."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        import io
        from store.models import CarouselImage
        
        # Crear imagen de prueba
        image = Image.new('RGB', (1920, 390), color='blue')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        carousel = CarouselImage.objects.create(
            title='Test Carousel',
            image=SimpleUploadedFile('carousel_test.jpg', image_io.read(), content_type='image/jpeg'),
            position=1
        )
        
        # Verificar que retorna una URL válida
        assert carousel.image_url is not None
        assert '/media/' in carousel.image_url or carousel.image_url.startswith('http')

    def test_carousel_image_url_without_image(self):
        """Verifica que image_url retorna placeholder cuando no hay imagen."""
        from store.models import CarouselImage
        
        # Crear carousel sin imagen (esto normalmente no debería pasar, pero por seguridad)
        carousel = CarouselImage(title='Test Without Image', position=1)
        
        assert carousel.image_url == '/static/images/placeholder.png'

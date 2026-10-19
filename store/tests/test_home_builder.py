import pytest
from django.urls import reverse
from store.models import Product, HomeSection, HomeSectionProduct, PromoBanner, CarouselImage
from category.models import Category
from store.services import HomeSectionService
from django.core.files.uploadedfile import SimpleUploadedFile

@pytest.mark.django_db
class TestHomeBuilder:
    
    @pytest.fixture
    def setup_data(self):
        self.category = Category.objects.create(category_name="Herramientas", slug="herramientas")
        mock_img1 = SimpleUploadedFile("taladro.png", b"file_content", content_type="image/png")
        self.product1 = Product.objects.create(
            name="Taladro", price=100, stock=10, code="T001", is_available=True, category=self.category, slug="taladro",
            images=mock_img1
        )
        mock_img2 = SimpleUploadedFile("lijadora.png", b"file_content", content_type="image/png")
        self.product2 = Product.objects.create(
            name="Lijadora", price=150, stock=5, code="L001", is_available=True, category=self.category, slug="lijadora",
            is_on_sale=True, sale_price=120, images=mock_img2
        )
        # Create a section
        self.section = HomeSection.objects.create(
            title="Carrusel Test",
            section_type="product_carousel",
            source_type="bestsellers",
            position=1
        )

    def test_source_type_bestsellers(self, setup_data):
        # Even without orders, check if it doesn't crash and returns empty if no orders
        products = HomeSectionService._resolve_products(self.section)
        assert isinstance(products, list)

    def test_manual_priority_over_auto(self, setup_data):
        # Set to bestsellers but add a manual product
        HomeSectionProduct.objects.create(section=self.section, product=self.product1, position=1)
        
        products = HomeSectionService._resolve_products(self.section)
        assert len(products) == 1
        assert products[0] == self.product1
        assert self.section.has_manual_products is True

    def test_promo_banner_links(self, setup_data):
        banner = PromoBanner.objects.create(
            section=self.section,
            title="Banner Test",
            image_desktop="photos/banners/test.jpg"
        )
        
        # Test URL priority
        banner.url = "https://google.com"
        assert banner.get_link_url() == "https://google.com"
        
        # Test Product priority
        banner.url = ""
        banner.link_product = self.product1
        assert banner.get_link_url() == self.product1.get_url()
        
        # Test Category priority
        banner.link_product = None
        banner.link_category = self.category
        banner.link_params = "?brand=stanley"
        assert banner.get_link_url() == f"{self.category.get_url()}?brand=stanley"

    def test_home_view_enriched_sections(self, client, setup_data):
        url = reverse('home')
        response = client.get(url)
        assert response.status_code == 200
        assert 'sections' in response.context
        
        sections = response.context['sections']
        assert len(sections) > 0
        assert 'section' in sections[0]
        assert 'data' in sections[0]

    def test_carousel_image_blank_null(self):
        # Verify CarouselImage can be saved without the 'image' field if asset is provided
        from media_bank.models import ImageAsset
        asset = ImageAsset.objects.create(name="Test Asset")
        
        carousel = CarouselImage.objects.create(
            title="Test Carousel",
            image_asset=asset,
            position=1
        )
        assert carousel.id is not None
        assert carousel.image_asset == asset
        assert not carousel.image # should be empty


@pytest.mark.django_db
class TestHomeSectionCommercialSanitation:
    """Valida los filtros de calidad comercial e integridad física de imagen en _resolve_products."""

    def test_auto_section_filters_missing_image_and_invalid_prices(self):
        category = Category.objects.create(category_name="Fijaciones", slug="fijaciones")
        section = HomeSection.objects.create(
            title="Novedades", section_type="product_carousel",
            source_type="newest", position=1, max_products=10
        )

        valid_img = SimpleUploadedFile("tornillo_ok.png", b"fake_content", content_type="image/png")

        # 1. Producto válido regular (debe incluirse)
        p_ok = Product.objects.create(
            code="OK-01", name="Tornillo Valido", slug="tornillo-valido",
            price=200.0, stock=10, is_available=True, category=category,
            images=valid_img
        )

        # 2. Producto sin imagen (debe excluirse)
        Product.objects.create(
            code="NO-IMG", name="Tornillo Sin Imagen", slug="tornillo-sin-imagen",
            price=200.0, stock=10, is_available=True, category=category
        )

        # 3. Producto con precio 0 y sin oferta (debe excluirse)
        img_zero = SimpleUploadedFile("zero.png", b"fake_content", content_type="image/png")
        Product.objects.create(
            code="PRICE-ZERO", name="Tornillo Precio Cero", slug="tornillo-precio-cero",
            price=0.0, stock=10, is_available=True, category=category,
            images=img_zero
        )

        # 4. Producto con oferta corrupta sale_price=0 (debe excluirse)
        img_corrupt = SimpleUploadedFile("corrupt.png", b"fake_content", content_type="image/png")
        Product.objects.create(
            code="CORRUPT-SALE", name="Tornillo Oferta Cero", slug="tornillo-oferta-cero",
            price=500.0, is_on_sale=True, sale_price=0.0, stock=10,
            is_available=True, category=category, images=img_corrupt
        )

        # 5. Producto en oferta con sale_price válido aunque price=0 (debe incluirse)
        img_sale = SimpleUploadedFile("sale_ok.png", b"fake_content", content_type="image/png")
        p_sale_ok = Product.objects.create(
            code="SALE-OK", name="Tornillo Oferta Valida", slug="tornillo-oferta-valida",
            price=0.0, is_on_sale=True, sale_price=150.0, stock=10,
            is_available=True, category=category, images=img_sale
        )

        products = HomeSectionService._resolve_products(section)
        codes = [p.code for p in products]

        assert "OK-01" in codes
        assert "SALE-OK" in codes
        assert "NO-IMG" not in codes
        assert "PRICE-ZERO" not in codes
        assert "CORRUPT-SALE" not in codes

    def test_manual_section_filters_invalid_commercial_products(self):
        category = Category.objects.create(category_name="Manual", slug="manual")
        section = HomeSection.objects.create(
            title="Manual Test", section_type="product_carousel",
            source_type="bestsellers", position=1, max_products=10
        )

        # Producto manual sin imagen asignada (debe ser filtrado)
        p_no_img = Product.objects.create(
            code="MANUAL-NO-IMG", name="Manual Sin Foto", slug="manual-sin-foto",
            price=300.0, stock=5, is_available=True, category=category
        )
        HomeSectionProduct.objects.create(section=section, product=p_no_img, position=1)

        # Producto manual con imagen válida (debe conservarse)
        img = SimpleUploadedFile("manual_ok.png", b"fake_content", content_type="image/png")
        p_ok = Product.objects.create(
            code="MANUAL-OK", name="Manual Con Foto", slug="manual-con-foto",
            price=300.0, stock=5, is_available=True, category=category,
            images=img
        )
        HomeSectionProduct.objects.create(section=section, product=p_ok, position=2)

        products = HomeSectionService._resolve_products(section)
        assert len(products) == 1
        assert products[0].code == "MANUAL-OK"

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
        self.product1 = Product.objects.create(
            name="Taladro", price=100, stock=10, code="T001", is_available=True, category=self.category, slug="taladro"
        )
        self.product2 = Product.objects.create(
            name="Lijadora", price=150, stock=5, code="L001", is_available=True, category=self.category, slug="lijadora",
            is_on_sale=True, sale_price=120
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

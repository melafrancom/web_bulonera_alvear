"""
test_feeds.py

QUÉ:
    Tests unitarios y de integración para la generación de feeds de productos:
    - Inclusión y límite de <g:additional_image_link> en Google Merchant feed.
    - Exclusión de imágenes placeholder (/static/...).
    - Resolución de ProductGallery.image_url (FK image_asset vs legacy image).
    - Prefetch y consistencia en FeedService.get_google_merchant_feed_data().
    - Salida XML válida tanto en vista web (/store/feeds/google-merchant/)
      como en vista API (/api/v1/store/feeds/google_merchant_xml/).

POR QUÉ:
    Garantizar que Google Merchant Center reciba todas las imágenes secundarias del catálogo
    sin penalizaciones, respetando el límite de 10 imágenes adicionales por producto y
    evitando N+1 queries en base de datos.
"""
from decimal import Decimal
from xml.etree import ElementTree as ET
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from store.models import Product, ProductGallery
from store.services import FeedService
from media_bank.models import ImageAsset, ImageType


@pytest.mark.django_db
class TestGoogleMerchantFeedData:
    """Tests unitarios de datos para Google Merchant Feed."""

    def test_product_gallery_image_url_resolves_fk_first(self, product):
        """
        QUÉ:
            Verifica que ProductGallery.image_url priorice image_asset sobre image legacy.
        POR QUÉ:
            Arquitectura híbrida Fase A: migración progresiva hacia el Banco de Imágenes.
        """
        mock_file = SimpleUploadedFile("gallery_fk.jpg", b"fake_fk_bytes", content_type="image/jpeg")
        asset = ImageAsset.objects.create(
            image_type=ImageType.PRODUCT,
            file=mock_file,
            name="Gallery FK Asset"
        )
        legacy_file = SimpleUploadedFile("gallery_legacy.jpg", b"fake_legacy_bytes", content_type="image/jpeg")

        gallery = ProductGallery.objects.create(
            product=product,
            image_asset=asset,
            image=legacy_file
        )

        # Debe resolver la URL del image_asset (o su WebP)
        assert gallery.image_url == (asset.get_webp_url() or asset.file.url)

    def test_product_gallery_image_url_fallback_to_legacy(self, product):
        """
        QUÉ:
            Verifica que ProductGallery.image_url haga fallback a image legacy si no hay image_asset.
        POR QUÉ:
            Compatibilidad con imágenes históricas aún no migradas.
        """
        legacy_file = SimpleUploadedFile("legacy_only.jpg", b"fake_legacy_bytes", content_type="image/jpeg")
        gallery = ProductGallery.objects.create(
            product=product,
            image=legacy_file
        )
        assert gallery.image_url == gallery.image.url

    def test_product_gallery_image_url_empty_when_no_image(self, product):
        """
        QUÉ:
            Verifica que ProductGallery.image_url retorne string vacío si no hay archivo.
        """
        gallery = ProductGallery(product=product)
        assert gallery.image_url == ''

    def test_get_merchant_data_includes_additional_image_links(self, product):
        """
        QUÉ:
            Verifica que Product.get_merchant_data() incluya additional_image_links con URLs absolutas.
        POR QUÉ:
            Google Merchant exige URLs absolutas (https://...) para imágenes adicionales.
        """
        for i in range(3):
            file_mock = SimpleUploadedFile(f"gallery_{i}.jpg", b"fake_img", content_type="image/jpeg")
            ProductGallery.objects.create(product=product, image=file_mock)

        merchant_data = product.get_merchant_data()

        assert 'additional_image_links' in merchant_data
        assert len(merchant_data['additional_image_links']) == 3
        for link in merchant_data['additional_image_links']:
            assert link.startswith(settings.SITE_URL)
            assert '/media/' in link

    def test_get_merchant_data_limits_to_10_additional_images(self, product):
        """
        QUÉ:
            Verifica que Product.get_merchant_data() limite a máximo 10 imágenes adicionales.
        POR QUÉ:
            Google Shopping restringe additional_image_link a un máximo de 10 por producto.
        """
        for i in range(15):
            file_mock = SimpleUploadedFile(f"gallery_limit_{i}.jpg", b"fake_img", content_type="image/jpeg")
            ProductGallery.objects.create(product=product, image=file_mock)

        merchant_data = product.get_merchant_data()

        assert len(merchant_data['additional_image_links']) == 10

    def test_get_merchant_data_excludes_placeholder_images(self, product):
        """
        QUÉ:
            Verifica que URLs con prefijo /static/ (placeholders) no se agreguen al feed.
        POR QUÉ:
            Google Merchant rechaza imágenes genéricas de placeholder.
        """
        gallery_item = ProductGallery.objects.create(
            product=product,
            image=SimpleUploadedFile("dummy.jpg", b"bytes", content_type="image/jpeg")
        )
        # Mockear image_url para retornar un placeholder estático
        with patch.object(ProductGallery, 'image_url', '/static/images/placeholder.png'):
            merchant_data = product.get_merchant_data()
            assert len(merchant_data['additional_image_links']) == 0

    def test_feed_service_fetches_merchant_feed_with_gallery(self, product):
        """
        QUÉ:
            Verifica que FeedService.get_google_merchant_feed_data() devuelva el producto
            con sus additional_image_links correctamente poblados.
        """
        file_mock = SimpleUploadedFile("feed_service_gal.jpg", b"fake_img", content_type="image/jpeg")
        ProductGallery.objects.create(product=product, image=file_mock)

        feed_items = FeedService.get_google_merchant_feed_data()

        product_item = next((item for item in feed_items if item['code'] == product.code), None)
        assert product_item is not None
        assert len(product_item.get('additional_image_links', [])) == 1


@pytest.mark.django_db
class TestGoogleMerchantFeedViews:
    """Tests de integración para los endpoints de feed XML."""

    def test_google_merchant_feed_web_view_xml_structure(self, client, product):
        """
        QUÉ:
            Valida que la vista web /store/feeds/google-merchant/ retorne XML válido con nodos <g:additional_image_link>.
        """
        file_mock = SimpleUploadedFile("web_view_gal.jpg", b"fake_img", content_type="image/jpeg")
        ProductGallery.objects.create(product=product, image=file_mock)

        url = reverse('store:google_merchant_feed')
        response = client.get(url)

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/xml'

        root = ET.fromstring(response.content)
        channel = root.find('channel')
        assert channel is not None

        items = channel.findall('item')
        assert len(items) >= 1

        # Verificar namespace Google Merchant
        namespaces = {'g': 'http://base.google.com/ns/1.0'}
        first_item = items[0]
        additional_links = first_item.findall('g:additional_image_link', namespaces)
        assert len(additional_links) == 1
        assert additional_links[0].text.startswith(settings.SITE_URL)

    def test_google_merchant_feed_api_view_xml_structure(self, client, product):
        """
        QUÉ:
            Valida que la vista API /api/v1/store/feeds/google_merchant_xml/ retorne XML con <g:additional_image_link>.
        """
        file_mock = SimpleUploadedFile("api_view_gal.jpg", b"fake_img", content_type="image/jpeg")
        ProductGallery.objects.create(product=product, image=file_mock)

        response = client.get('/api/v1/store/feeds/google_merchant_xml/')

        assert response.status_code == 200
        assert response['Content-Type'] == 'application/xml'

        root = ET.fromstring(response.content)
        channel = root.find('channel')
        assert channel is not None

        namespaces = {'g': 'http://base.google.com/ns/1.0'}
        items = channel.findall('item')
        assert len(items) >= 1

        first_item = items[0]
        additional_links = first_item.findall('g:additional_image_link', namespaces)
        assert len(additional_links) == 1
        assert additional_links[0].text.startswith(settings.SITE_URL)

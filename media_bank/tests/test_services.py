"""
Tests unitarios y de integración para la capa de servicios de media_bank.
"""
import io
import pytest
from PIL import Image

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from media_bank.models import ImageAsset, ImageType
from media_bank.services import MediaBankService


@pytest.fixture
def valid_image_file():
    """Genera un archivo de imagen en memoria válido para pruebas."""
    img = Image.new('RGB', (60, 60), color='teal')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return SimpleUploadedFile('servicio_test.jpg', buf.read(), content_type='image/jpeg')


@pytest.mark.django_db
class TestMediaBankService:
    """Pruebas del servicio centralizado MediaBankService."""

    def test_create_image_success(self, valid_image_file):
        """Verifica la creación exitosa de un ImageAsset mediante el servicio."""
        asset = MediaBankService.create_image(
            file=valid_image_file,
            image_type=ImageType.PRODUCT,
            name='Tornillo Cabeza Hexagonal',
            alt_text='Tornillo hexagonal de acero'
        )

        assert asset.pk is not None
        assert asset.name == 'Tornillo Cabeza Hexagonal'
        assert asset.alt_text == 'Tornillo hexagonal de acero'
        assert asset.image_type == ImageType.PRODUCT
        assert ImageAsset.objects.filter(pk=asset.pk).exists()

    def test_create_image_auto_defaults_metadata(self, valid_image_file):
        """Si name y alt_text no se proveen, deben generarse automáticamente."""
        asset = MediaBankService.create_image(
            file=valid_image_file,
            image_type=ImageType.CAROUSEL
        )

        assert asset.pk is not None
        assert asset.name == 'servicio_test'
        assert 'Bulonera Alvear' in asset.alt_text

    def test_create_image_fails_and_rolls_back_on_invalid_file(self):
        """Un archivo no válido debe fallar la validación full_clean y no persistirse."""
        fake_file = SimpleUploadedFile('malicious.jpg', b'THIS_IS_NOT_AN_IMAGE', content_type='image/jpeg')

        initial_count = ImageAsset.objects.count()

        with pytest.raises(ValidationError):
            MediaBankService.create_image(
                file=fake_file,
                image_type=ImageType.PRODUCT
            )

        # REGLA: Ningún registro huérfano debe persistir tras fallar la validación
        assert ImageAsset.objects.count() == initial_count

    def test_get_images_by_type_filtering(self, valid_image_file):
        """Verifica que el servicio filtre correctamente por ImageType."""
        # Crear 2 productos y 1 banner
        MediaBankService.create_image(file=valid_image_file, image_type=ImageType.PRODUCT)

        img2 = Image.new('RGB', (10, 10))
        buf2 = io.BytesIO()
        img2.save(buf2, format='JPEG')
        buf2.seek(0)
        file2 = SimpleUploadedFile('prod2.jpg', buf2.read(), content_type='image/jpeg')
        MediaBankService.create_image(file=file2, image_type=ImageType.PRODUCT)

        img3 = Image.new('RGB', (10, 10))
        buf3 = io.BytesIO()
        img3.save(buf3, format='JPEG')
        buf3.seek(0)
        file3 = SimpleUploadedFile('banner1.jpg', buf3.read(), content_type='image/jpeg')
        MediaBankService.create_image(file=file3, image_type=ImageType.BANNER)

        product_assets = MediaBankService.get_images_by_type(ImageType.PRODUCT)
        banner_assets = MediaBankService.get_images_by_type(ImageType.BANNER)

        assert product_assets.count() == 2
        assert banner_assets.count() == 1
        assert all(a.image_type == ImageType.PRODUCT for a in product_assets)
        assert all(a.image_type == ImageType.BANNER for a in banner_assets)

    def test_get_all_images(self, valid_image_file):
        """Verifica que get_all_images retorne todas las imágenes."""
        MediaBankService.create_image(file=valid_image_file, image_type=ImageType.PRODUCT)
        all_images = MediaBankService.get_all_images()
        assert all_images.count() >= 1

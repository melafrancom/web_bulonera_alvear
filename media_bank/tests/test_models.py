"""Tests for Media Bank Models"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
import io
from media_bank.models import ImageAsset


@pytest.mark.django_db
class TestImageAssetModel:
    """Tests del modelo ImageAsset."""

    def test_create_image_asset(self):
        """Verifica que se puede crear un ImageAsset correctamente."""
        # Crear imagen de prueba
        image = Image.new('RGB', (100, 100), color='blue')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        asset = ImageAsset.objects.create(
            file=SimpleUploadedFile('test_image.jpg', image_io.read(), content_type='image/jpeg'),
            name='Test Image',
            alt_text='Test alt text'
        )
        
        assert asset.name == 'Test Image'
        assert asset.alt_text == 'Test alt text'
        assert asset.file is not None

    def test_auto_name_from_file(self):
        """Verifica que el nombre se genera automáticamente del archivo."""
        # Crear imagen de prueba
        image = Image.new('RGB', (100, 100), color='green')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        asset = ImageAsset.objects.create(
            file=SimpleUploadedFile('my_product_image.jpg', image_io.read(), content_type='image/jpeg')
        )
        
        # El nombre debe ser generado del filename sin extensión
        assert asset.name == 'my_product_image'

    def test_thumbnail_url(self):
        """Verifica que thumbnail_url retorna la URL correcta."""
        # Crear imagen de prueba
        image = Image.new('RGB', (100, 100), color='red')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        
        asset = ImageAsset.objects.create(
            file=SimpleUploadedFile('thumbnail_test.jpg', image_io.read(), content_type='image/jpeg')
        )
        
        # Debe retornar una URL válida
        assert asset.thumbnail_url is not None
        assert '/media/' in asset.thumbnail_url or asset.thumbnail_url.startswith('http')

    def test_thumbnail_url_without_file(self):
        """Verifica que thumbnail_url retorna placeholder sin archivo."""
        asset = ImageAsset()
        assert asset.thumbnail_url == '/static/images/placeholder.png'

    def test_str_representation(self):
        """Verifica la representación en string."""
        asset = ImageAsset(name='Test Asset')
        assert str(asset) == 'Test Asset'

    def test_auto_alt_text_and_helpers(self):
        """Verifica la autogeneración de alt_text y el correcto funcionamiento de los métodos SEO/GEO/AEO."""
        image = Image.new('RGB', (100, 100), color='yellow')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)

        asset = ImageAsset.objects.create(
            file=SimpleUploadedFile('bulon_hexagonal.jpg', image_io.read(), content_type='image/jpeg')
        )
        assert asset.name == 'bulon_hexagonal'
        assert asset.alt_text == 'bulon_hexagonal - Bulonera Alvear'

        # SEO Alt text
        assert asset.get_seo_alt_text('Bulón Hexagonal 1/2') == 'Bulón Hexagonal 1/2 - Bulonera Alvear Resistencia'

        # GEO & Voice summaries
        geo_summary = asset.get_geo_summary()
        assert 'bulon_hexagonal' in geo_summary
        assert 'Bulonera Alvear' in geo_summary

        voice_summary = asset.get_voice_summary()
        assert 'bulon_hexagonal' in voice_summary

        # Schema Data
        schema_data = asset.get_schema_data('https://buloneraalvear.com.ar')
        assert schema_data['@type'] == 'ImageObject'
        assert schema_data['name'] == 'bulon_hexagonal'
        assert 'contentUrl' in schema_data

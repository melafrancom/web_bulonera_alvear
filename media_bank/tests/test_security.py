"""
Tests de seguridad AppSec y validaciones defensivas para media_bank.

Cubre:
- Path Traversal (AUD-MB-001 / CWE-22)
- Sanitización de nombres de archivo y normalización de extensiones
- Detección de ejecutables camuflados y validación de Magic Bytes
- Prevención de Stored XSS en interfaces de administración (AUD-MB-002)
"""
import io
import pytest
from PIL import Image

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile

from media_bank.upload_utils import (
    overwrite_upload_path,
    create_clean_filename,
    validate_image_file,
    MAX_IMAGE_SIZE_BYTES,
)
from media_bank.admin import ImageAssetAdmin
from media_bank.models import ImageAsset, ImageType


# ---------------------------------------------------------------------------
# 1. Tests de Path Traversal y Confinamiento de Rutas (AUD-MB-001)
# ---------------------------------------------------------------------------

class TestPathTraversalSecurity:
    """Verifica que ninguna operación de subida pueda escapar de settings.MEDIA_ROOT."""

    def test_overwrite_upload_path_blocks_parent_directory_traversal(self):
        """Intento de navegación hacia directorio padre debe levantar SuspiciousFileOperation."""
        malicious_paths = [
            '../../etc/passwd',
            '../../../manage.py',
            'photos/products/../../../../root_file.txt',
            '..\\..\\windows\\system32\\cmd.exe',
            '/etc/shadow',
        ]
        for path in malicious_paths:
            with pytest.raises(SuspiciousFileOperation):
                overwrite_upload_path(path)

    def test_overwrite_upload_path_allows_safe_relative_paths(self):
        """Rutas legítimas dentro de MEDIA_ROOT se confinan y normalizan correctamente."""
        safe_relative = 'photos/products/original/tornillo_1.jpg'
        result = overwrite_upload_path(safe_relative)
        assert result == 'photos/products/original/tornillo_1.jpg'
        assert not result.startswith('/')


# ---------------------------------------------------------------------------
# 2. Tests de Sanitización de Nombres de Archivo
# ---------------------------------------------------------------------------

class TestFilenameSanitization:
    """Verifica la normalización de nombres y extensiones."""

    def test_create_clean_filename_transliterates_accents_and_lowercases_extension(self):
        filename = "Cárátulá de Póst 2026.PNG"
        clean = create_clean_filename(filename)
        assert clean == "Caratula-de-Post-2026.png"

    def test_create_clean_filename_removes_dangerous_characters(self):
        filename = 'foto;rm -rf /;$(whoami).jpg'
        clean = create_clean_filename(filename)
        assert ';' not in clean
        assert '$' not in clean
        assert '(' not in clean
        assert clean.endswith('.jpg')

    def test_create_clean_filename_handles_empty_or_only_symbols(self):
        filename = '???###$$$.jpg'
        clean = create_clean_filename(filename)
        assert clean == 'asset.jpg'


# ---------------------------------------------------------------------------
# 3. Tests de Validación Estricta de Imágenes (Magic Bytes y DoS)
# ---------------------------------------------------------------------------

class TestImageValidationSecurity:
    """Verifica la validación de cabecera binaria real y protección anti-DoS."""

    def test_validate_image_file_accepts_valid_jpeg(self):
        img = Image.new('RGB', (50, 50), color='blue')
        buffer = io.BytesIO()
        img.save(buffer, format='JPEG')
        buffer.seek(0)

        uploaded = SimpleUploadedFile('valid.jpg', buffer.read(), content_type='image/jpeg')
        # No debe lanzar excepción
        validate_image_file(uploaded)

    def test_validate_image_file_rejects_fake_image_magic_bytes(self):
        """Un script shell o PHP camuflado con extensión .jpg debe ser rechazado."""
        fake_content = b"<?php phpinfo(); ?> -- this is not a real image"
        uploaded = SimpleUploadedFile('shell.jpg', fake_content, content_type='image/jpeg')

        with pytest.raises(ValidationError) as exc_info:
            validate_image_file(uploaded)
        assert "no es una imagen válida" in str(exc_info.value)

    def test_validate_image_file_rejects_unallowed_extension(self):
        """Archivos con extensiones potencialmente peligrosas deben ser rechazados."""
        img = Image.new('RGB', (10, 10))
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        uploaded = SimpleUploadedFile('script.svg', buffer.read(), content_type='image/svg+xml')
        with pytest.raises(ValidationError) as exc_info:
            validate_image_file(uploaded)
        assert "Extensión no permitida" in str(exc_info.value)

    def test_validate_image_file_rejects_oversized_file(self):
        """Archivos que superen MAX_IMAGE_SIZE_BYTES deben ser rechazados."""
        uploaded = SimpleUploadedFile('giant.jpg', b'dummy', content_type='image/jpeg')
        uploaded.size = MAX_IMAGE_SIZE_BYTES + 1024

        with pytest.raises(ValidationError) as exc_info:
            validate_image_file(uploaded)
        assert "excede el tamaño máximo permitido" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 4. Tests de Prevención de Stored XSS en Admin (AUD-MB-002)
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestAdminXSSProtection:
    """Verifica que los previews en ImageAssetAdmin escapen caracteres maliciosos."""

    def test_thumbnail_preview_escapes_xss_in_alt_and_url(self, rf):
        from django.contrib.admin.sites import AdminSite
        admin = ImageAssetAdmin(ImageAsset, AdminSite())

        # Crear asset con caracteres maliciosos en alt_text
        img = Image.new('RGB', (10, 10))
        buf = io.BytesIO()
        img.save(buf, format='JPEG')
        buf.seek(0)

        malicious_alt = '<script>alert("xss")</script>" onmouseover="alert(1)'
        asset = ImageAsset(
            file=SimpleUploadedFile('test.jpg', buf.read(), content_type='image/jpeg'),
            name='Test',
            alt_text=malicious_alt
        )

        preview_html = str(admin.thumbnail_preview(asset))
        preview_large_html = str(admin.thumbnail_preview_large(asset))

        # Las etiquetas <script> y comillas maliciosas deben estar escapadas a entidades HTML
        assert '<script>' not in preview_html
        assert '&lt;script&gt;' in preview_html
        assert '<script>' not in preview_large_html
        assert '&lt;script&gt;' in preview_large_html

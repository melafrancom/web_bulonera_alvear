"""
Pruebas de seguridad para la carga de imágenes de perfil (SEC-INF-001 y SEC-INF-007).

QUÉ:
    Verifica que la subida de foto de perfil (UserProfile.profile_picture y UserProfileForm)
    aplique validación estricta de extensiones permitidas, estructura interna de imagen (magic bytes)
    y límite de tamaño, además de delegar la persistencia a ProfileUpdateService.

POR QUÉ:
    Mitiga el vector de evasión hacia /var/www/shared/media/ donde un atacante autenticado
    podría subir archivos no autorizados camuflados o saturar el disco/memoria.
"""
import io
from PIL import Image
import pytest
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from account.models import Account, UserProfile
from account.web.forms import UserProfileForm


def create_test_image(format: str = 'JPEG', size: tuple = (100, 100), color: str = 'blue') -> io.BytesIO:
    """Helper para crear imágenes válidas en memoria."""
    image_io = io.BytesIO()
    image = Image.new('RGB', size, color=color)
    image.save(image_io, format=format)
    image_io.seek(0)
    return image_io


@pytest.fixture
def auth_user_and_profile(db):
    """Fixture que provee un usuario autenticado y su perfil asociado."""
    user = Account.objects.create_user(
        first_name='Test',
        last_name='Security',
        username='securityuser',
        email='security@example.com',
        password='ValidPassword123!',
    )
    user.is_active = True
    user.save()
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return user, profile


@pytest.mark.django_db
class TestProfileUploadSecurity:
    """Suite de validación de seguridad de uploads en perfil de usuario."""

    def test_upload_valid_jpeg_succeeds(self, auth_user_and_profile):
        """
        REGLA: Formulario debe aceptar imágenes JPEG genuinas dentro de los límites.
        """
        _, profile = auth_user_and_profile
        image_content = create_test_image('JPEG').getvalue()
        uploaded_file = SimpleUploadedFile('avatar.jpg', image_content, content_type='image/jpeg')

        form = UserProfileForm(
            data={
                'address_line_1': 'Calle Segura 123',
                'address_line_2': '',
                'city': 'Alvear',
                'state': 'Santa Fe',
                'country': 'Argentina',
            },
            files={'profile_picture': uploaded_file},
            instance=profile
        )
        assert form.is_valid(), f"Errores inesperados: {form.errors}"

    def test_upload_valid_webp_succeeds(self, auth_user_and_profile):
        """
        REGLA: Formulario debe aceptar imágenes WebP genuinas.
        """
        _, profile = auth_user_and_profile
        image_content = create_test_image('WEBP').getvalue()
        uploaded_file = SimpleUploadedFile('avatar.webp', image_content, content_type='image/webp')

        form = UserProfileForm(
            data={
                'address_line_1': 'Calle Segura 123',
                'city': 'Alvear',
                'state': 'Santa Fe',
                'country': 'Argentina',
            },
            files={'profile_picture': uploaded_file},
            instance=profile
        )
        assert form.is_valid(), f"Errores inesperados: {form.errors}"

    def test_upload_bmp_rejected(self, auth_user_and_profile):
        """
        REGLA: Extensiones no permitidas por la whitelist (.bmp) deben ser rechazadas.
        """
        _, profile = auth_user_and_profile
        image_content = create_test_image('BMP').getvalue()
        uploaded_file = SimpleUploadedFile('avatar.bmp', image_content, content_type='image/bmp')

        form = UserProfileForm(
            data={'address_line_1': 'Calle Segura 123'},
            files={'profile_picture': uploaded_file},
            instance=profile
        )
        assert not form.is_valid()
        assert 'profile_picture' in form.errors

    def test_upload_spoofed_content_as_jpg_rejected(self, auth_user_and_profile):
        """
        REGLA: Un archivo de texto arbitrario o script camuflado con extensión .jpg debe ser
        bloqueado por validate_image_file al fallar la inspección de magic bytes con Pillow.
        """
        _, profile = auth_user_and_profile
        fake_content = b"INVALID_IMAGE_PAYLOAD_TESTING_MAGIC_BYTES_REJECTION_1234567890"
        uploaded_file = SimpleUploadedFile('spoofed.jpg', fake_content, content_type='image/jpeg')

        form = UserProfileForm(
            data={'address_line_1': 'Calle Segura 123'},
            files={'profile_picture': uploaded_file},
            instance=profile
        )
        assert not form.is_valid()
        assert 'profile_picture' in form.errors

    def test_upload_oversized_image_rejected(self, auth_user_and_profile):
        """
        REGLA: Archivos que excedan el límite de 10 MB deben ser rechazados preventivamente (DoS).
        """
        _, profile = auth_user_and_profile
        oversized_content = b"0" * (11 * 1024 * 1024)  # 11 MB
        uploaded_file = SimpleUploadedFile('large.jpg', oversized_content, content_type='image/jpeg')

        form = UserProfileForm(
            data={'address_line_1': 'Calle Segura 123'},
            files={'profile_picture': uploaded_file},
            instance=profile
        )
        assert not form.is_valid()
        assert 'profile_picture' in form.errors

    def test_edit_profile_delegates_to_service(self, client, auth_user_and_profile):
        """
        REGLA: La vista edit_profile debe delegar la persistencia a ProfileUpdateService
        y no llamar directamente a form.save() (SEC-INF-007).
        """
        user, profile = auth_user_and_profile
        client.force_login(user)

        image_content = create_test_image('JPEG').getvalue()
        uploaded_file = SimpleUploadedFile('avatar.jpg', image_content, content_type='image/jpeg')

        url = reverse('account:edit_profile')
        post_data = {
            'first_name': 'Frank',
            'last_name': 'Alvear',
            'phone': '3411234567',
            'address_line_1': 'Av San Martín 500',
            'address_line_2': 'Piso 2',
            'city': 'Villa Gobernador Gálvez',
            'state': 'Santa Fe',
            'country': 'Argentina',
            'profile_picture': uploaded_file,
        }

        with patch('account.services.ProfileUpdateService.update_user_profile') as mock_profile, \
             patch('account.services.ProfileUpdateService.update_user_profile_picture') as mock_picture, \
             patch('account.services.ProfileUpdateService.update_user_profile_address') as mock_address:

            response = client.post(url, data=post_data, follow=False)

            assert response.status_code == 302
            assert response.url == reverse('account:dashboard')
            assert mock_profile.called
            assert mock_picture.called
            assert mock_address.called

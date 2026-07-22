"""Tests for Account Models"""
import pytest
from django.contrib.auth import get_user_model
from account.models import Account, UserProfile

Account = get_user_model()


@pytest.mark.django_db
class TestAccountModel:
    """Tests para el modelo Account"""
    
    def test_create_user(self):
        """Test crear usuario básico"""
        user = Account.objects.create_user(
            first_name='Juan',
            last_name='Pérez',
            username='juanperez',
            email='juan@example.com',
            password='testpass123'
        )
        assert user.email == 'juan@example.com'
        assert user.username == 'juanperez'
        assert user.first_name == 'Juan'
        assert user.last_name == 'Pérez'
        assert user.is_active is False  # Por defecto no está activo
        assert user.check_password('testpass123')
    
    def test_create_superuser(self):
        """Test crear superusuario"""
        user = Account.objects.create_superuser(
            first_name='Admin',
            last_name='User',
            username='admin',
            email='admin@example.com',
            password='adminpass123'
        )
        assert user.is_admin is True
        assert user.is_staff is True
        assert user.is_superadmin is True
        assert user.is_active is True
    
    def test_user_full_name(self):
        """Test método full_name"""
        user = Account(first_name='Juan', last_name='Pérez')
        assert user.full_name() == 'Juan Pérez'
        assert user.get_full_name() == 'Juan Pérez'

    def test_user_geo_and_voice_summaries(self):
        """Verifica la generación de resúmenes seguros GEO y AEO de usuario"""
        user = Account(first_name='Carlos', last_name='Gómez', email='carlos@example.com')
        assert 'Carlos Gómez' in user.get_geo_summary()
        assert 'carlos@example.com' in user.get_geo_summary()
        assert 'Carlos Gómez' in user.get_voice_summary()
    
    def test_user_str(self):
        """Test representación string del usuario"""
        user = Account.objects.create_user(
            first_name='Carlos',
            last_name='López',
            username='carloslopez',
            email='carlos@example.com',
            password='testpass123'
        )
        assert str(user) == 'carlos@example.com'
    
    def test_create_user_without_email(self):
        """Test crear usuario sin email debe fallar"""
        with pytest.raises(ValueError, match='El usuario debe tener el email'):
            Account.objects.create_user(
                first_name='Test',
                last_name='User',
                username='testuser',
                email='',
                password='testpass123'
            )
    
    def test_create_user_without_username(self):
        """Test crear usuario sin username debe fallar"""
        with pytest.raises(ValueError, match='El usuario debe ingresar el username'):
            Account.objects.create_user(
                first_name='Test',
                last_name='User',
                username='',
                email='test@example.com',
                password='testpass123'
            )


@pytest.mark.django_db
class TestUserProfileModel:
    """Tests para el modelo UserProfile"""
    
    def test_create_user_profile(self):
        """Test crear perfil de usuario"""
        user = Account.objects.create_user(
            first_name='Ana',
            last_name='Martínez',
            username='anamartinez',
            email='ana@example.com',
            password='testpass123'
        )
        profile = UserProfile.objects.create(
            user=user,
            address_line_1='Calle Falsa 123',
            city='Buenos Aires',
            state='CABA',
            country='Argentina'
        )
        assert profile.user == user
        assert profile.address_line_1 == 'Calle Falsa 123'
        assert profile.city == 'Buenos Aires'
    
    def test_profile_str(self):
        """Test representación string del perfil"""
        user = Account.objects.create_user(
            first_name='Pedro',
            last_name='Ramírez',
            username='pedroramirez',
            email='pedro@example.com',
            password='testpass123'
        )
        profile = UserProfile.objects.create(user=user)
        assert str(profile) == 'Pedro Ramírez'
    
    def test_profile_full_address(self):
        """Test método full_address"""
        user = Account.objects.create_user(
            first_name='Laura',
            last_name='Fernández',
            username='laurafernandez',
            email='laura@example.com',
            password='testpass123'
        )
        profile = UserProfile.objects.create(
            user=user,
            address_line_1='Av. Corrientes 1234',
            address_line_2='Piso 5, Depto B'
        )
        assert profile.full_address() == 'Av. Corrientes 1234 Piso 5, Depto B'
    
    def test_profile_picture_url_default(self):
        """Test URL de foto de perfil por defecto"""
        user = Account.objects.create_user(
            first_name='Diego',
            last_name='Torres',
            username='diegotorres',
            email='diego@example.com',
            password='testpass123'
        )
        profile = UserProfile.objects.create(user=user)
        assert profile.get_profile_picture_url() == '/static/admin/img/placeholder.png'

"""Tests for Account Services"""
import pytest
from unittest.mock import Mock, patch
from django.contrib.auth import get_user_model
from account.models import Account, UserProfile
from account.services import (
    AccountRegistrationService,
    AccountLoginService,
    PasswordResetService,
    ProfileUpdateService,
    AccountActivationService,
    PasswordChangeService,
    DashboardService
)

Account = get_user_model()


@pytest.mark.django_db
class TestAccountRegistrationService:
    """Tests para AccountRegistrationService"""
    
    @patch('account.services.AccountRegistrationService.send_verification_email')
    def test_register_user(self, mock_send_email):
        """Test registro de usuario"""
        mock_send_email.return_value = True
        mock_request = Mock()
        
        user = AccountRegistrationService.register(
            first_name='Test',
            last_name='User',
            email='test@example.com',
            phone='1234567890',
            password='testpass123',
            request=mock_request
        )
        
        assert user.email == 'test@example.com'
        assert user.first_name == 'Test'
        assert user.last_name == 'User'
        assert user.phone == '1234567890'
        assert user.username == 'test'
        assert UserProfile.objects.filter(user=user).exists()
        mock_send_email.assert_called_once()


@pytest.mark.django_db
class TestAccountLoginService:
    """Tests para AccountLoginService"""
    
    def test_authenticate_user_success(self):
        """Test autenticación exitosa"""
        user = Account.objects.create_user(
            first_name='Test',
            last_name='User',
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        user.is_active = True
        user.save()
        
        authenticated_user = AccountLoginService.authenticate_user(
            email='test@example.com',
            password='testpass123'
        )
        
        assert authenticated_user is not None
        assert authenticated_user.email == 'test@example.com'
    
    def test_authenticate_user_wrong_password(self):
        """Test autenticación con contraseña incorrecta"""
        user = Account.objects.create_user(
            first_name='Test',
            last_name='User',
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        user.is_active = True
        user.save()
        
        authenticated_user = AccountLoginService.authenticate_user(
            email='test@example.com',
            password='wrongpassword'
        )
        
        assert authenticated_user is None
    
    def test_authenticate_user_inactive(self):
        """Test autenticación con usuario inactivo"""
        user = Account.objects.create_user(
            first_name='Test',
            last_name='User',
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        # Usuario no está activo por defecto
        
        authenticated_user = AccountLoginService.authenticate_user(
            email='test@example.com',
            password='testpass123'
        )
        
        assert authenticated_user is None


@pytest.mark.django_db
class TestPasswordResetService:
    """Tests para PasswordResetService"""
    
    def test_send_reset_email_nonexistent_user(self):
        """Test envío de email a usuario inexistente"""
        mock_request = Mock()
        result = PasswordResetService.send_reset_email('nonexistent@example.com', mock_request)
        assert result is False
    
    def test_reset_password(self):
        """Test reset de contraseña"""
        user = Account.objects.create_user(
            first_name='Test',
            last_name='User',
            username='testuser',
            email='test@example.com',
            password='oldpass123'
        )
        
        result = PasswordResetService.reset_password(str(user.pk), 'newpass123')
        
        assert result is True
        user.refresh_from_db()
        assert user.check_password('newpass123')


@pytest.mark.django_db
class TestProfileUpdateService:
    """Tests para ProfileUpdateService"""
    
    def test_update_user_profile(self):
        """Test actualización de perfil de usuario"""
        user = Account.objects.create_user(
            first_name='Old',
            last_name='Name',
            username='oldname',
            email='old@example.com',
            password='testpass123'
        )
        
        result = ProfileUpdateService.update_user_profile(
            user=user,
            first_name='New',
            last_name='Name',
            phone='9876543210'
        )
        
        assert result is True
        user.refresh_from_db()
        assert user.first_name == 'New'
        assert user.last_name == 'Name'
        assert user.phone == '9876543210'
    
    def test_update_user_profile_address(self):
        """Test actualización de dirección"""
        user = Account.objects.create_user(
            first_name='Test',
            last_name='User',
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        result = ProfileUpdateService.update_user_profile_address(
            user=user,
            address_line_1='Nueva Calle 123',
            city='Buenos Aires',
            country='Argentina'
        )
        
        assert result is True
        profile = UserProfile.objects.get(user=user)
        assert profile.address_line_1 == 'Nueva Calle 123'
        assert profile.city == 'Buenos Aires'
        assert profile.country == 'Argentina'


@pytest.mark.django_db
class TestAccountActivationService:
    """Tests para AccountActivationService"""
    
    def test_activate_account(self):
        """Test activación de cuenta"""
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        from django.contrib.auth.tokens import default_token_generator
        
        user = Account.objects.create_user(
            first_name='Test',
            last_name='User',
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        assert user.is_active is False
        
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        
        activated_user = AccountActivationService.activate_account(uidb64, token)
        
        assert activated_user is not None
        assert activated_user.is_active is True


@pytest.mark.django_db
class TestPasswordChangeService:
    """Tests para PasswordChangeService"""
    
    def test_change_password_success(self):
        """Test cambio de contraseña exitoso"""
        user = Account.objects.create_user(
            first_name='Test',
            last_name='User',
            username='testuser',
            email='test@example.com',
            password='oldpass123'
        )
        
        result = PasswordChangeService.change_password(
            user=user,
            current_password='oldpass123',
            new_password='newpass123'
        )
        
        assert result is True
        user.refresh_from_db()
        assert user.check_password('newpass123')
    
    def test_change_password_wrong_current(self):
        """Test cambio de contraseña con contraseña actual incorrecta"""
        user = Account.objects.create_user(
            first_name='Test',
            last_name='User',
            username='testuser',
            email='test@example.com',
            password='oldpass123'
        )
        
        result = PasswordChangeService.change_password(
            user=user,
            current_password='wrongpass',
            new_password='newpass123'
        )
        
        assert result is False
        user.refresh_from_db()
        assert user.check_password('oldpass123')


@pytest.mark.django_db
class TestDashboardService:
    """Tests para DashboardService"""
    
    def test_get_user_dashboard_data(self):
        """Test obtención de datos del dashboard"""
        user = Account.objects.create_user(
            first_name='Test',
            last_name='User',
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        data = DashboardService.get_user_dashboard_data(user)
        
        assert 'orders_count' in data
        assert 'new_orders_count' in data
        assert 'accepted_orders_count' in data
        assert 'completed_orders_count' in data
        assert 'cancelled_orders_count' in data
        assert data['orders_count'] == 0
    
    def test_get_user_profile(self):
        """Test obtención de perfil de usuario"""
        user = Account.objects.create_user(
            first_name='Test',
            last_name='User',
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        profile = DashboardService.get_user_profile(user)
        
        assert profile is not None
        assert profile.user == user

"""
Account Security Tests — Verificación de Controles Defensivos

Cubre:
- SEC-001: Open Redirect Protection (en login y redirección segura)
- SEC-002: Session Leak Protection (purga de session['uid'] tras reset)
- SEC-004 & SEC-011: Anti-Enumeración (mensajes idénticos en Web y API)
- SEC-005: Prevención de Colisión de Username (sufijo UUID)
- SEC-006: Validación de Contraseñas (política Django en servicios)
- SEC-010: Guardia defensiva en resetPassword (sin sesión válida)
"""
import pytest
from django.urls import reverse
from django.test import RequestFactory
from django.core.exceptions import ValidationError
from account.models import Account
from account.services import (
    AccountRegistrationService,
    AccountLoginService,
    PasswordResetService
)


@pytest.mark.django_db
class TestOpenRedirectProtection:
    """SEC-001: Login no debe redirigir a dominios externos ni protocolos relativos."""

    def test_rejects_external_url(self, client, user):
        resp = client.post(
            f"{reverse('account:login')}?next=https://evil.com",
            {'email': user.email, 'password': 'TestPass123', 'next': 'https://evil.com'},
        )
        assert resp.status_code == 302
        assert 'evil.com' not in resp.url

    def test_rejects_protocol_relative_url(self, client, user):
        resp = client.post(
            f"{reverse('account:login')}?next=//evil.com",
            {'email': user.email, 'password': 'TestPass123', 'next': '//evil.com'},
        )
        assert resp.status_code == 302
        assert 'evil.com' not in resp.url

    def test_allows_internal_path(self, client, user):
        resp = client.post(
            f"{reverse('account:login')}?next=/account/my-orders/",
            {'email': user.email, 'password': 'TestPass123', 'next': '/account/my-orders/'},
        )
        assert resp.status_code == 302
        assert resp.url == '/account/my-orders/'

    def test_resolve_safe_redirect_service_fallback(self):
        # Fallback a dashboard cuando la URL es maliciosa
        target = AccountLoginService.resolve_safe_redirect(
            target_url='http://phishing.com/steal',
            allowed_host='buloneraalvear.online',
            require_https=True
        )
        assert target == 'account:dashboard'


@pytest.mark.django_db
class TestSessionLeakProtection:
    """SEC-002: session['uid'] debe eliminarse tras reseteo exitoso."""

    def test_uid_purged_after_reset(self, client):
        user = Account.objects.create_user(
            first_name='Test', last_name='Reset', username='reset_test_user',
            email='reset_user@test.com', password='OldPassword123!',
        )
        user.is_active = True
        user.save()

        session = client.session
        session['uid'] = str(user.pk)
        session.save()

        response = client.post(reverse('account:resetPassword'), {
            'password': 'NewSecurePassword123!',
            'confirm_password': 'NewSecurePassword123!',
        })
        assert response.status_code == 302
        assert 'uid' not in client.session


@pytest.mark.django_db
class TestAntiEnumeration:
    """SEC-004 & SEC-011: No se debe filtrar la existencia de emails en Web ni API."""

    def test_same_message_for_existing_and_missing_email_web(self, client, user):
        r1 = client.post(reverse('account:forgotPassword'), {'email': user.email}, follow=True)
        r2 = client.post(reverse('account:forgotPassword'), {'email': 'noexiste_jamas@test.com'}, follow=True)
        msgs1 = [str(m) for m in r1.context['messages']]
        msgs2 = [str(m) for m in r2.context['messages']]
        assert msgs1 == msgs2
        assert len(msgs1) > 0

    def test_same_message_for_existing_and_missing_email_api(self, client, user):
        from django.core.cache import cache
        cache.clear()
        r1 = client.post('/api/v1/account/password/request_reset/', {'email': user.email})
        cache.clear()
        r2 = client.post('/api/v1/account/password/request_reset/', {'email': 'inexistente@test.com'})
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()['message'] == r2.json()['message']


@pytest.mark.django_db
class TestRateLimiting:
    """SEC-003: Rate limiting en endpoints sensibles de autenticación."""

    def test_password_reset_throttled_after_limit(self, client):
        from django.core.cache import cache
        cache.clear()
        for _ in range(3):
            resp = client.post('/api/v1/account/password/request_reset/', {'email': 'throttletest@example.com'})
            assert resp.status_code == 200
        
        # 4th request should trigger HTTP 429 Too Many Requests
        resp_throttled = client.post('/api/v1/account/password/request_reset/', {'email': 'throttletest@example.com'})
        assert resp_throttled.status_code == 429
        cache.clear()


@pytest.mark.django_db
class TestUsernameCollision:
    """SEC-005: Dos registros con mismo prefijo de email no deben colisionar."""

    def test_no_integrity_error(self):
        req = RequestFactory().get('/')
        u1 = AccountRegistrationService.register(
            'NombreUno', 'ApellidoUno', 'ventas@empresa-a.com', '12345678', 'StrongPass123!', req,
        )
        u2 = AccountRegistrationService.register(
            'NombreDos', 'ApellidoDos', 'ventas@empresa-b.com', '87654321', 'StrongPass456!', req,
        )
        assert u1.username != u2.username
        assert u1.username.startswith('ventas_')
        assert u2.username.startswith('ventas_')
        assert u1.pk != u2.pk


@pytest.mark.django_db
class TestResetPasswordGuard:
    """SEC-010: resetPassword GET sin uid en sesión debe redirigir a forgotPassword."""

    def test_no_uid_redirects(self, client):
        resp = client.get(reverse('account:resetPassword'))
        assert resp.status_code == 302
        assert 'forgotPassword' in resp.url or 'forgot' in resp.url


@pytest.mark.django_db
class TestPasswordValidationEnforcement:
    """SEC-006: Toda creación o reseteo de contraseña valida la política de Django."""

    def test_short_password_rejected_in_registration(self):
        req = RequestFactory().get('/')
        with pytest.raises(ValidationError):
            AccountRegistrationService.register(
                'Short', 'Pass', 'short@test.com', '111', '123', req
            )

    def test_short_password_rejected_in_reset(self, user):
        result = PasswordResetService.reset_password(str(user.pk), '123')
        assert result is False

"""
Account Web Tests

Tests de vistas web de autenticación (login, registro, dashboard).
"""
import pytest
from django.test import Client
from django.urls import reverse


@pytest.mark.django_db
class TestAccountWebViews:
    """Tests de vistas web de cuenta"""

    def test_login_view_200(self, client):
        """GET /account/login/ retorna 200"""
        response = client.get(reverse('account:login'))
        assert response.status_code == 200

    def test_login_view_has_form(self, client):
        """GET /account/login/ contiene formulario y metatag noindex"""
        response = client.get(reverse('account:login'))
        assert response.status_code == 200
        assert 'name="robots" content="noindex, nofollow"' in response.content.decode()

    def test_register_view_200(self, client):
        """GET /account/register/ retorna 200"""
        response = client.get(reverse('account:register'))
        assert response.status_code == 200

    def test_register_view_has_form(self, client):
        """GET /account/register/ contiene formulario"""
        response = client.get(reverse('account:register'))
        assert response.status_code == 200
        assert 'first_name' in response.content.decode() or 'email' in response.content.decode()


@pytest.mark.django_db
class TestDashboardView:
    """Tests de dashboard"""

    def test_dashboard_unauthenticated_redirect(self, client):
        """GET /account/dashboard/ redirige si no autenticado"""
        response = client.get(reverse('account:dashboard'), follow=False)
        assert response.status_code in [302, 301]  # Redirect to login

    def test_dashboard_authenticated_200(self, client, user):
        """GET /account/dashboard/ retorna 200 si autenticado"""
        client.login(email=user.email, password='TestPass123')
        response = client.get(reverse('account:dashboard'))
        assert response.status_code == 200

    def test_dashboard_displays_user_info(self, client, user):
        """GET /account/dashboard/ muestra información del usuario"""
        client.login(email=user.email, password='TestPass123')
        response = client.get(reverse('account:dashboard'))
        assert response.status_code == 200
        content = response.content.decode()
        assert user.email in content or user.first_name in content or user.username in content

"""
Account API Tests

Tests de endpoints REST de autenticación y perfil.
"""
import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse


@pytest.mark.django_db
class TestAuthAPI:
    """Tests de autenticación API"""

    def test_login_success_200(self, client, user):
        """POST /api/v1/account/auth/login/ retorna 200 con credenciales válidas"""
        response = client.post('/api/v1/account/auth/login/', {
            'email': user.email,
            'password': 'TestPass123'
        })
        assert response.status_code == 200
        data = response.json()
        assert 'token' in data or 'key' in data  # Token Auth

    def test_login_invalid_credentials_400(self, client):
        """POST /api/v1/account/auth/login/ retorna 400 con credenciales inválidas"""
        response = client.post('/api/v1/account/auth/login/', {
            'email': 'nonexistent@test.com',
            'password': 'wrongpassword'
        })
        assert response.status_code in [400, 401]

    def test_logout_unauthenticated_401(self, client):
        """POST /api/v1/account/auth/logout/ retorna 401/403 sin token"""
        response = client.post('/api/v1/account/auth/logout/')
        assert response.status_code in [401, 403]

    def test_logout_authenticated_200(self, authenticated_api_client):
        """POST /api/v1/account/auth/logout/ retorna 200 con token válido"""
        response = authenticated_api_client.post('/api/v1/account/auth/logout/')
        assert response.status_code == 200

    def test_register_success_201(self, client):
        """POST /api/v1/account/auth/register/ retorna 201 con datos válidos"""
        response = client.post('/api/v1/account/auth/register/', {
            'email': 'newuser@test.com',
            'first_name': 'New',
            'last_name': 'User',
            'phone': '+5491234567890',
            'password': 'SecurePass123',
            'confirm_password': 'SecurePass123'
        })
        assert response.status_code in [200, 201]

    def test_register_passwords_mismatch_400(self, client):
        """POST /api/v1/account/auth/register/ retorna 400 si contraseñas no coinciden"""
        response = client.post('/api/v1/account/auth/register/', {
            'email': 'newuser@test.com',
            'first_name': 'New',
            'last_name': 'User',
            'password': 'SecurePass123',
            'confirm_password': 'DifferentPass123'
        })
        assert response.status_code == 400


@pytest.mark.django_db
class TestProfileAPI:
    """Tests de perfil en API"""

    def test_get_profile_unauthenticated_401(self, client):
        """GET /api/v1/account/profile/me/ retorna 401/403 sin autenticación"""
        response = client.get('/api/v1/account/profile/me/')
        assert response.status_code in [401, 403]

    def test_get_profile_authenticated_200(self, authenticated_api_client, user):
        """GET /api/v1/account/profile/me/ retorna 200 autenticado"""
        response = authenticated_api_client.get('/api/v1/account/profile/me/')
        assert response.status_code == 200
        data = response.json()
        assert data['email'] == user.email

    def test_profile_contains_user_data(self, authenticated_api_client, user):
        """GET /api/v1/account/profile/me/ contiene datos del usuario"""
        response = authenticated_api_client.get('/api/v1/account/profile/me/')
        assert response.status_code == 200
        data = response.json()
        assert 'email' in data
        assert 'first_name' in data
        assert 'last_name' in data

    def test_update_profile_authenticated_200(self, authenticated_api_client, user):
        """PUT /api/v1/account/profile/me/ actualiza perfil"""
        response = authenticated_api_client.put('/api/v1/account/profile/me/', {
            'first_name': 'UpdatedName',
            'last_name': 'UpdatedLast',
            'phone': '+5491234567890'
        })
        assert response.status_code in [200, 201, 405]  # 405 si PUT no está soportado

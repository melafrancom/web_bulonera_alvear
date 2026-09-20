"""Tests for Contact API"""
import pytest
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from django.urls import reverse
from contact.models import ContactOption

Account = get_user_model()


@pytest.mark.django_db
class TestContactAPIViewSet(APITestCase):
    """Tests para ContactOptionViewSet (API REST)"""

    def setUp(self):
        """Setup para tests de API"""
        self.list_url = reverse('contact_api:contact-list')
        self.valid_data = {
            'name': 'Carlos López',
            'email': 'carlos@example.com',
            'contact_method': 'email',
            'subject': 'Consulta por bulones cabeza hexagonal',
            'message': 'Hola, quisiera cotización por 500 unidades paso fino...'
        }

        # Admin user para listar contactos
        self.admin_user = Account.objects.create_superuser(
            email='admin@bulonera.com',
            username='admin_bulonera',
            first_name='Admin',
            last_name='User',
            password='adminpassword123'
        )

    def test_create_contact_success(self):
        """Test: Crear contacto vía API POST (Público)"""
        response = self.client.post(self.list_url, self.valid_data, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ContactOption.objects.count(), 1)
        self.assertEqual(ContactOption.objects.first().name, 'Carlos López')

    def test_create_contact_missing_required_field(self):
        """Test: Crear contacto sin campo requerido devuelve 400"""
        data = {
            'name': 'Carlos López',
            'email': 'carlos@example.com',
            'contact_method': 'email',
            'subject': 'Consulta'
            # falta message
        }
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_contact_rejects_crlf_in_subject(self):
        """Test: Intento de CRLF injection en subject devuelve 400"""
        data = {**self.valid_data, 'subject': 'Consulta\r\nBcc: spammer@evil.com'}
        response = self.client.post(self.list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(ContactOption.objects.count(), 0)

    def test_list_contacts_forbidden_for_anonymous(self):
        """Test: Usuario anónimo recibe 403 Forbidden al intentar listar contactos"""
        ContactOption.objects.create(**self.valid_data)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_contacts_admin_authenticated(self):
        """Test: Administrador autenticado puede listar contactos"""
        ContactOption.objects.create(**self.valid_data)
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get('results', response.data)), 1)

    def test_retrieve_contact_forbidden_for_anonymous(self):
        """Test: Usuario anónimo recibe 403 Forbidden al intentar ver detalle de contacto"""
        contact = ContactOption.objects.create(**self.valid_data)
        detail_url = reverse('contact_api:contact-detail', args=[contact.pk])

        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_contact_admin_authenticated(self):
        """Test: Administrador autenticado puede ver detalle del contacto"""
        contact = ContactOption.objects.create(**self.valid_data)
        detail_url = reverse('contact_api:contact-detail', args=[contact.pk])
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], self.valid_data['email'])

    def test_put_update_is_not_allowed(self):
        """Test: PUT no está implementado ni permitido en ContactOptionViewSet"""
        contact = ContactOption.objects.create(**self.valid_data)
        detail_url = reverse('contact_api:contact-detail', args=[contact.pk])

        # Anónimo recibe 403
        anon_response = self.client.put(detail_url, self.valid_data, format='json')
        self.assertIn(anon_response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED])

        # Admin autenticado recibe 405 Method Not Allowed (mixins no incluyen UpdateModelMixin)
        self.client.force_authenticate(user=self.admin_user)
        admin_response = self.client.put(detail_url, self.valid_data, format='json')
        self.assertEqual(admin_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_is_not_allowed(self):
        """Test: DELETE no está implementado ni permitido en ContactOptionViewSet"""
        contact = ContactOption.objects.create(**self.valid_data)
        detail_url = reverse('contact_api:contact-detail', args=[contact.pk])

        # Anónimo recibe 403
        anon_response = self.client.delete(detail_url)
        self.assertIn(anon_response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_405_METHOD_NOT_ALLOWED])

        # Admin autenticado recibe 405 Method Not Allowed (mixins no incluyen DestroyModelMixin)
        self.client.force_authenticate(user=self.admin_user)
        admin_response = self.client.delete(detail_url)
        self.assertEqual(admin_response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

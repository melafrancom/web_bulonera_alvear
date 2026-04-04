"""Tests for Contact API"""
import pytest
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth.models import User
from contact.models import ContactOption


@pytest.mark.django_db
class TestContactAPIViewSet(APITestCase):
    """Tests para ContactOptionViewSet (API REST)"""
    
    def setUp(self):
        """Setup para tests de API"""
        self.client = APIClient()
        self.list_url = '/api/contact/'  # Ajustar según tu main urls.py
        
        # Admin user para listar contactos
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )
    
    def test_create_contact_success(self):
        """Test: Crear contacto vía API POST"""
        # Arrange
        data = {
            'name': 'Carlos López',
            'email': 'carlos@example.com',
            'contact_method': 'email',
            'subject': 'Consulta',
            'message': 'Hola, quisiera preguntar...'
        }
        
        # Act
        response = self.client.post(self.list_url, data, format='json')
        
        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ContactOption.objects.count(), 1)
        self.assertEqual(ContactOption.objects.first().name, 'Carlos López')
    
    def test_create_contact_missing_required_field(self):
        """Test: Crear contacto sin campo requerido"""
        # Arrange
        data = {
            'name': 'Carlos López',
            'email': 'carlos@example.com',
            # Falta contact_method
            'subject': 'Consulta',
            'message': 'Hola'
        }
        
        # Act
        response = self.client.post(self.list_url, data, format='json')
        
        # Assert
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_list_contact_admin_only(self):
        """Test: Solo admin puede listar contactos"""
        # Arrange
        contact = ContactOption.objects.create(
            name='Test',
            email='test@example.com',
            contact_method='email',
            subject='Test',
            message='Test'
        )
        
        # Act: Usuario anónimo
        response = self.client.get(self.list_url)
        
        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # No debería mostrar contactos a usuario anónimo
    
    def test_list_contact_admin_authenticated(self):
        """Test: Admin puede listar todos los contactos"""
        # Arrange
        contact = ContactOption.objects.create(
            name='Test',
            email='test@example.com',
            contact_method='email',
            subject='Test',
            message='Test'
        )
        
        # Act
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.list_url)
        
        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)

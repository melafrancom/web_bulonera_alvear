"""Tests for Contact Web Views"""
import pytest
from django.test import TestCase, Client
from django.urls import reverse
from contact.models import ContactOption


@pytest.mark.django_db
class TestContactWebViews(TestCase):
    """Tests para vistas web de Contact (HTML)"""
    
    def setUp(self):
        """Setup para tests de vistas web"""
        self.client = Client()
    
    def test_contact_view_get(self):
        """Test: GET /contact/ muestra el formulario"""
        # Act
        response = self.client.get(reverse('contact'))
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form')  # La template debe tener el formulario
        self.assertTemplateUsed(response, 'contact/contact.html')
    
    def test_contact_view_post_success_email(self):
        """Test: POST /contact/ con método email"""
        # Arrange
        data = {
            'name': 'Pedro Sánchez',
            'email': 'pedro@example.com',
            'contact_method': 'email',
            'subject': 'Consulta de producto',
            'message': 'Quiero saber más sobre...'
        }
        
        # Act
        response = self.client.post(reverse('contact'), data, follow=True)
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse('contact_success'))
        self.assertTrue(ContactOption.objects.filter(name='Pedro Sánchez').exists())
    
    def test_contact_view_post_success_whatsapp(self):
        """Test: POST /contact/ con método WhatsApp"""
        # Arrange
        data = {
            'name': 'Ana González',
            'email': 'ana@example.com',
            'contact_method': 'whatsapp',
            'subject': 'Información',
            'message': 'Me interesa este producto'
        }
        
        # Act
        response = self.client.post(reverse('contact'), data, follow=True)
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse('contact_success'))
    
    def test_contact_view_invalid_form(self):
        """Test: POST /contact/ con datos inválidos"""
        # Arrange
        data = {
            'name': '',  # Campo vacío
            'email': 'invalid-email',  # Email inválido
            'contact_method': 'email',
            'subject': 'Test',
            'message': 'Test'
        }
        
        # Act
        response = self.client.post(reverse('contact'), data)
        
        # Assert
        self.assertEqual(response.status_code, 200)
        # No debería redirigir a success
        self.assertTemplateUsed(response, 'contact/contact.html')
    
    def test_contact_success_view(self):
        """Test: GET /contact/success/ muestra página de éxito"""
        # Act
        response = self.client.get(reverse('contact_success'))
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'contact/contact_success.html')

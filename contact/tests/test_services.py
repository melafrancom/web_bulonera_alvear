"""Tests for Contact Services"""
import pytest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.core.mail import EmailMessage
from contact.models import ContactOption
from contact.services import ContactService


@pytest.mark.django_db
class TestContactService(TestCase):
    """Tests para ContactService"""
    
    def setUp(self):
        """Setup para tests del servicio"""
        self.valid_data = {
            'name': 'María García',
            'email': 'maria@example.com',
            'contact_method': 'email',
            'subject': 'Solicitud de información',
            'message': 'Me gustaría saber más sobre...'
        }
    
    def test_create_contact_success(self):
        """Test: Crear contacto exitosamente con método email"""
        # Arrange & Act
        with patch.object(ContactService, 'send_email_notification', return_value=True):
            contact = ContactService.create_contact(**self.valid_data)
        
        # Assert
        self.assertIsNotNone(contact.id)
        self.assertEqual(contact.name, self.valid_data['name'])
        self.assertEqual(contact.email, self.valid_data['email'])
        self.assertTrue(ContactOption.objects.filter(id=contact.id).exists())
    
    def test_create_contact_missing_field(self):
        """Test: Crear contacto sin campo requerido genera ValueError"""
        # Arrange
        invalid_data = self.valid_data.copy()
        invalid_data['name'] = ''  # Campo vacío
        
        # Act & Assert
        with self.assertRaises(ValueError):
            ContactService.create_contact(**invalid_data)
    
    def test_create_contact_invalid_method(self):
        """Test: Crear contacto con método inválido genera ValueError"""
        # Arrange
        invalid_data = self.valid_data.copy()
        invalid_data['contact_method'] = 'telegram'  # Método no válido
        
        # Act & Assert
        with self.assertRaises(ValueError):
            ContactService.create_contact(**invalid_data)
    
    @patch('contact.services.EmailMessage.send')
    def test_send_email_notification_success(self, mock_send):
        """Test: Enviar email exitosamente"""
        # Arrange
        contact = ContactOption.objects.create(**self.valid_data)
        mock_send.return_value = 1  # Simular envío exitoso
        
        # Act
        result = ContactService.send_email_notification(contact)
        
        # Assert
        self.assertTrue(result)
        mock_send.assert_called_once()
    
    @patch('contact.services.EmailMessage.send')
    def test_send_email_notification_failure(self, mock_send):
        """Test: Fallar al enviar email"""
        # Arrange
        contact = ContactOption.objects.create(**self.valid_data)
        mock_send.side_effect = Exception("SMTP Error")
        
        # Act
        result = ContactService.send_email_notification(contact)
        
        # Assert
        self.assertFalse(result)
    
    def test_process_whatsapp_contact(self):
        """Test: Procesar contacto por WhatsApp (logging)"""
        # Arrange
        whatsapp_data = self.valid_data.copy()
        whatsapp_data['contact_method'] = 'whatsapp'
        
        # Act
        with patch.object(ContactService, 'process_whatsapp_contact'):
            with patch('contact.services.logger'):
                contact = ContactService.create_contact(**whatsapp_data)
        
        # Assert
        self.assertEqual(contact.contact_method, 'whatsapp')
    
    def test_format_email_body(self):
        """Test: Formato del cuerpo del email"""
        # Arrange
        contact = ContactOption.objects.create(**self.valid_data)
        
        # Act
        body = ContactService._format_email_body(contact)
        
        # Assert
        self.assertIn(contact.name, body)
        self.assertIn(contact.email, body)
        self.assertIn(contact.subject, body)
        self.assertIn(contact.message, body)

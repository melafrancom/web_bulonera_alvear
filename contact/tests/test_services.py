"""Tests for Contact Services"""
import pytest
from unittest.mock import patch
from django.test import TestCase
from django.core.cache import cache
from contact.models import ContactOption
from contact.services import ContactService, ContactRateLimited


@pytest.mark.django_db
class TestContactService(TestCase):
    """Tests para ContactService"""

    def setUp(self):
        """Setup para tests del servicio"""
        cache.clear()
        self.valid_data = {
            'name': 'María García',
            'email': 'maria@example.com',
            'contact_method': 'email',
            'subject': 'Solicitud de información',
            'message': 'Me gustaría saber más sobre tornillos autoperforantes.'
        }

    def tearDown(self):
        cache.clear()

    @patch('contact.tasks.send_contact_notification_task.delay')
    def test_create_contact_success(self, mock_delay):
        """Test: Crear contacto exitosamente encola la tarea Celery tras el commit"""
        with self.captureOnCommitCallbacks(execute=True):
            contact = ContactService.create_contact(**self.valid_data)

        self.assertIsNotNone(contact.id)
        self.assertEqual(contact.name, self.valid_data['name'])
        self.assertEqual(contact.email, self.valid_data['email'])
        self.assertTrue(ContactOption.objects.filter(id=contact.id).exists())
        mock_delay.assert_called_once_with(contact.id)

    @patch('contact.tasks.send_contact_notification_task.delay')
    def test_create_contact_whatsapp_enqueues_notification(self, mock_delay):
        """Test: Contacto por WhatsApp también encola la tarea Celery de notificación unificada tras el commit"""
        whatsapp_data = {**self.valid_data, 'contact_method': 'whatsapp'}
        with self.captureOnCommitCallbacks(execute=True):
            contact = ContactService.create_contact(**whatsapp_data)

        self.assertEqual(contact.contact_method, 'whatsapp')
        mock_delay.assert_called_once_with(contact.id)

    def test_create_contact_missing_field(self):
        """Test: Crear contacto sin campo requerido genera ValueError"""
        invalid_data = self.valid_data.copy()
        invalid_data['name'] = ''

        with self.assertRaises(ValueError):
            ContactService.create_contact(**invalid_data)

    def test_create_contact_invalid_method(self):
        """Test: Crear contacto con método inválido genera ValueError"""
        invalid_data = self.valid_data.copy()
        invalid_data['contact_method'] = 'telegram'

        with self.assertRaises(ValueError):
            ContactService.create_contact(**invalid_data)

    def test_create_contact_rejects_crlf_in_name(self):
        """Test: Inyección CRLF en nombre falla validación y no persiste"""
        invalid_data = {**self.valid_data, 'name': 'María\r\nBcc: victim@example.com'}

        with self.assertRaises(ValueError):
            ContactService.create_contact(**invalid_data)
        self.assertEqual(ContactOption.objects.count(), 0)

    def test_create_contact_rejects_crlf_in_subject(self):
        """Test: Inyección CRLF en asunto falla validación y no persiste"""
        invalid_data = {**self.valid_data, 'subject': 'Consulta\nBcc: hacker@example.com'}

        with self.assertRaises(ValueError):
            ContactService.create_contact(**invalid_data)
        self.assertEqual(ContactOption.objects.count(), 0)

    def test_check_rate_limit_allows_under_limit(self):
        """Test: Rate limit permite solicitudes hasta el umbral"""
        ip = '10.0.0.1'
        for _ in range(ContactService.MAX_SUBMISSIONS_PER_HOUR):
            ContactService.check_rate_limit(ip)

    def test_check_rate_limit_blocks_after_max(self):
        """Test: Rate limit lanza ContactRateLimited al superar el máximo por hora"""
        ip = '10.0.0.2'
        for _ in range(ContactService.MAX_SUBMISSIONS_PER_HOUR):
            ContactService.check_rate_limit(ip)

        with self.assertRaises(ContactRateLimited):
            ContactService.check_rate_limit(ip)

    @patch('contact.services.EmailMessage.send')
    def test_send_email_notification_success(self, mock_send):
        """Test: Enviar email exitosamente con reply_to configurado"""
        contact = ContactOption.objects.create(**self.valid_data)
        mock_send.return_value = 1

        result = ContactService.send_email_notification(contact)

        self.assertTrue(result)
        mock_send.assert_called_once()

    @patch('contact.services.EmailMessage.send')
    def test_send_email_notification_failure(self, mock_send):
        """Test: Fallo en envío SMTP retorna False sin propagar excepción al caller"""
        contact = ContactOption.objects.create(**self.valid_data)
        mock_send.side_effect = Exception("SMTP Connection Timeout")

        result = ContactService.send_email_notification(contact)

        self.assertFalse(result)

    def test_format_email_body(self):
        """Test: Formato del cuerpo del email incluye canal preferido"""
        contact = ContactOption.objects.create(**self.valid_data)
        body = ContactService._format_email_body(contact)

        self.assertIn(contact.name, body)
        self.assertIn(contact.email, body)
        self.assertIn(contact.subject, body)
        self.assertIn(contact.message, body)
        self.assertIn('Canal preferido de respuesta', body)

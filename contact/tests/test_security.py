"""Security tests for Contact app (Anti-abuse, Rate Limiting, Honeypot, CRLF)."""
import pytest
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse
from contact.models import ContactOption


@pytest.mark.django_db
class TestContactSecurity(TestCase):
    """Pruebas de seguridad y robustez contra abuso y spam en la app contact."""

    def setUp(self):
        self.client = Client()
        cache.clear()
        self.contact_url = reverse('contact:contact')
        self.valid_data = {
            'name': 'Pedro Ramírez',
            'email': 'pedro@taller-ramirez.com.ar',
            'contact_method': 'email',
            'subject': 'Consulta por electrodos 6013',
            'message': 'Necesito precio por caja de electrodos 2.5mm.',
        }

    def tearDown(self):
        cache.clear()

    def test_honeypot_filled_drops_message_silently(self):
        """SEC: Si un bot rellena el campo trampa 'website', se finge éxito sin crear registro"""
        # Arrange
        payload = {
            **self.valid_data,
            'website': 'https://bot-spammer-phishing.com/viagra',
        }

        # Act
        response = self.client.post(self.contact_url, payload)

        # Assert
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('contact:contact_success'), response.url)
        self.assertEqual(ContactOption.objects.count(), 0)

    def test_honeypot_empty_creates_contact_normally(self):
        """SEC: Si el campo 'website' está vacío (usuario legítimo), se procesa el contacto"""
        # Arrange
        payload = {
            **self.valid_data,
            'website': '',
        }

        # Act
        response = self.client.post(self.contact_url, payload)

        # Assert
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ContactOption.objects.count(), 1)

    def test_web_rate_limiting_returns_429_after_threshold(self):
        """SEC: Más de 5 envíos en 1 hora desde la misma IP devuelven HTTP 429"""
        # Arrange
        client_ip = '181.44.120.5'

        # Act & Assert: Primeros 5 envíos permitidos
        for i in range(5):
            res = self.client.post(self.contact_url, self.valid_data, REMOTE_ADDR=client_ip)
            self.assertEqual(res.status_code, 302, f"Envío {i+1} debió ser exitoso")

        self.assertEqual(ContactOption.objects.count(), 5)

        # Act: 6to intento excede límite
        blocked_res = self.client.post(self.contact_url, self.valid_data, REMOTE_ADDR=client_ip)

        # Assert
        self.assertEqual(blocked_res.status_code, 429)
        self.assertEqual(ContactOption.objects.count(), 5)

    def test_rate_limiting_respects_x_forwarded_for_first_ip(self):
        """SEC: La IP del cliente real se extrae del primer valor de X-Forwarded-For (detrás de OLS)"""
        # Arrange
        headers = {'HTTP_X_FORWARDED_FOR': '200.5.10.15, 127.0.0.1'}

        # Act: 5 envíos permitidos
        for _ in range(5):
            res = self.client.post(self.contact_url, self.valid_data, **headers)
            self.assertEqual(res.status_code, 302)

        # Act: 6to envío desde la misma IP real
        blocked_res = self.client.post(self.contact_url, self.valid_data, **headers)

        # Assert
        self.assertEqual(blocked_res.status_code, 429)

    def test_crlf_injection_in_name_rejected_by_model_and_form(self):
        """SEC: Inyección CRLF en nombre no pasa validación del formulario ni crea contacto"""
        # Arrange
        malicious_data = {
            **self.valid_data,
            'name': 'Hacker\r\nBcc: victima@bulonera.com',
        }

        # Act
        response = self.client.post(self.contact_url, malicious_data)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactOption.objects.count(), 0)

    def test_crlf_injection_in_subject_rejected_by_model_and_form(self):
        """SEC: Inyección CRLF en asunto no pasa validación del formulario ni crea contacto"""
        # Arrange
        malicious_data = {
            **self.valid_data,
            'subject': 'Oferta especial\nSubject: Injected Subject\nBcc: target@test.com',
        }

        # Act
        response = self.client.post(self.contact_url, malicious_data)

        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactOption.objects.count(), 0)

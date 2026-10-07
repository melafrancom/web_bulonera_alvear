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
        response = self.client.get(reverse('contact:contact'))
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form')  # La template debe tener el formulario
        self.assertTemplateUsed(response, 'contact/contact.html')

    def test_contact_view_has_canonical_and_localbusiness_schema(self):
        """Verifica que /contact/ incluya rel=canonical y el Schema LocalBusiness/HardwareStore"""
        response = self.client.get(reverse('contact:contact'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('rel="canonical"', content)
        self.assertIn('"@type": "HardwareStore"', content)
        self.assertIn('Resistencia', content)
    
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
        response = self.client.post(reverse('contact:contact'), data, follow=True)
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse('contact:contact_success'))
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
        response = self.client.post(reverse('contact:contact'), data, follow=True)
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse('contact:contact_success'))
    
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
        response = self.client.post(reverse('contact:contact'), data)
        
        # Assert
        self.assertEqual(response.status_code, 200)
        # No debería redirigir a success
        self.assertTemplateUsed(response, 'contact/contact.html')
    
    def test_contact_success_view(self):
        """Test: GET /contact/success/ muestra página de éxito"""
        # Act
        response = self.client.get(reverse('contact:contact_success'))
        
        # Assert
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'contact/contact_success.html')

    def test_whatsapp_lead_redirect_enqueues_capi_lead_and_redirects(self):
        """
        QUÉ:
            Verifica que GET /contact/whatsapp-lead/ invoque enqueue_generate_lead con fallback
            por defecto 'whatsapp' y redirija adecuadamente hacia la URL de WhatsApp.
        POR QUÉ:
            Permite medir conversiones de WhatsApp de forma server-side (Meta CAPI) sin romper si falta source.
        """
        from unittest.mock import patch

        # Arrange
        url = reverse('contact:whatsapp_lead_redirect') + '?text=Hola&event_id=wa-test-uuid-123'

        # Act
        with patch('contact.web.views.views.MetaCapiService.enqueue_generate_lead') as mock_lead:
            response = self.client.get(url)

            # Assert
            self.assertEqual(response.status_code, 302)
            self.assertTrue(response.url.startswith('https://wa.me/'))
            self.assertIn('text=Hola', response.url)
            mock_lead.assert_called_once()
            call_kwargs = mock_lead.call_args
            self.assertEqual(call_kwargs.kwargs.get('lead_method') or call_kwargs[1].get('lead_method'), 'whatsapp')
            self.assertEqual(call_kwargs.kwargs.get('event_id') or call_kwargs[1].get('event_id'), 'wa-test-uuid-123')

    def test_whatsapp_lead_redirect_with_dynamic_source(self):
        """
        QUÉ:
            Verifica que GET /contact/whatsapp-lead/ extraiga el parámetro ?source= y lo envíe
            a Meta CAPI como lead_method.
        POR QUÉ:
            Garantiza granularidad en reportes de Meta Ads Manager para attribution por canal/sección.
        """
        from unittest.mock import patch

        # Arrange
        url = reverse('contact:whatsapp_lead_redirect') + '?text=Hola&event_id=wa-test-uuid-999&source=product_detail'

        # Act
        with patch('contact.web.views.views.MetaCapiService.enqueue_generate_lead') as mock_lead:
            response = self.client.get(url)

            # Assert
            self.assertEqual(response.status_code, 302)
            mock_lead.assert_called_once()
            call_kwargs = mock_lead.call_args
            self.assertEqual(call_kwargs.kwargs.get('lead_method') or call_kwargs[1].get('lead_method'), 'product_detail')
            self.assertEqual(call_kwargs.kwargs.get('event_id') or call_kwargs[1].get('event_id'), 'wa-test-uuid-999')



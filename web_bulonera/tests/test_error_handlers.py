"""Tests for Custom Error Handlers (400, 403, 404, 500)"""
import pytest
from django.test import Client, TestCase
from django.urls import reverse


@pytest.mark.django_db
class TestErrorHandlers(TestCase):
    """Tests para los manejadores de error HTTP de web_bulonera."""

    def setUp(self):
        self.client = Client()

    def test_handler404_status_and_noindex(self):
        """Verifica que la vista 404 retorne HTTP status 404 e incluya noindex, nofollow."""
        response = self.client.get('/pagina-inexistente-12345/')
        assert response.status_code == 404
        content = response.content.decode('utf-8')
        assert 'name="robots" content="noindex, nofollow"' in content
        assert 'Página no encontrada (404)' in content

    def test_handler500_template_has_noindex(self):
        """Verifica la renderización directa de 500.html con noindex, nofollow."""
        from django.template.loader import render_to_string
        rendered = render_to_string('errors/500.html')
        assert 'name="robots" content="noindex, nofollow"' in rendered
        assert 'Error del Servidor (500)' in rendered

    def test_handler403_template_has_noindex(self):
        """Verifica la renderización directa de 403.html con noindex, nofollow."""
        from django.template.loader import render_to_string
        rendered = render_to_string('errors/403.html')
        assert 'name="robots" content="noindex, nofollow"' in rendered
        assert 'Acceso Denegado (403)' in rendered

    def test_handler400_template_has_noindex(self):
        """Verifica la renderización directa de 400.html con noindex, nofollow."""
        from django.template.loader import render_to_string
        rendered = render_to_string('errors/400.html')
        assert 'name="robots" content="noindex, nofollow"' in rendered
        assert 'Solicitud Incorrecta (400)' in rendered

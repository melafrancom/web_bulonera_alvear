"""Tests for web_bulonera views"""
import pytest
from django.test import TestCase, Client
from django.urls import reverse
from category.models import Category


class TestLlmsTxtView(TestCase):
    """Tests para la vista llms.txt"""

    def setUp(self):
        self.client = Client()
        # Crear categorías de prueba
        Category.objects.create(
            category_name='Tornillos',
            slug='tornillos',
            description='Tornillos varios'
        )
        Category.objects.create(
            category_name='Tuercas',
            slug='tuercas',
            description='Tuercas varias'
        )

    def test_llms_txt_status_200(self):
        """Verifica que llms.txt retorna 200."""
        response = self.client.get('/llms.txt')
        assert response.status_code == 200

    def test_llms_txt_content_type(self):
        """Verifica que el content-type es text/markdown."""
        response = self.client.get('/llms.txt')
        assert 'text/markdown' in response['Content-Type']

    def test_llms_txt_contains_categories(self):
        """Verifica que llms.txt contiene las categorías."""
        response = self.client.get('/llms.txt')
        content = response.content.decode('utf-8')
        
        assert 'Tornillos' in content
        assert 'Tuercas' in content
        assert '/store/category/tornillos/' in content
        assert '/store/category/tuercas/' in content

    def test_llms_txt_contains_business_info(self):
        """Verifica que contiene información del negocio."""
        response = self.client.get('/llms.txt')
        content = response.content.decode('utf-8')
        
        assert 'Bulonera Alvear' in content
        assert 'Resistencia, Chaco, Argentina' in content
        assert 'Ferretería industrial' in content

    def test_llms_txt_contains_main_pages(self):
        """Verifica que contiene las páginas principales."""
        response = self.client.get('/llms.txt')
        content = response.content.decode('utf-8')
        
        assert 'Catálogo completo' in content
        assert 'Ofertas' in content
        assert 'Contacto' in content
        assert '/store/' in content
        assert '/contact/' in content


class TestRobotsTxtView(TestCase):
    """Tests para la vista robots.txt"""

    def setUp(self):
        self.client = Client()

    def test_robots_txt_status_200(self):
        """Verifica que robots.txt retorna 200."""
        response = self.client.get('/robots.txt')
        assert response.status_code == 200

    def test_robots_txt_contains_llms_hint(self):
        """Verifica que robots.txt contiene el hint para llms.txt."""
        response = self.client.get('/robots.txt')
        content = response.content.decode('utf-8')
        
        assert 'Llms-Txt:' in content
        assert '/llms.txt' in content


class TestAdsTxtView(TestCase):
    """Tests para la vista ads.txt"""

    def setUp(self):
        self.client = Client()

    def test_ads_txt_status_200(self):
        """Verifica que ads.txt retorna 200."""
        response = self.client.get('/ads.txt')
        assert response.status_code == 200

    def test_ads_txt_content_type(self):
        """Verifica que el content-type es text/plain con charset utf-8."""
        response = self.client.get('/ads.txt')
        assert 'text/plain' in response['Content-Type']
        assert 'utf-8' in response['Content-Type'].lower()

    def test_ads_txt_contains_ad_records(self):
        """Verifica que contiene los registros correctos de AdSense y cabecera IAB."""
        response = self.client.get('/ads.txt')
        content = response.content.decode('utf-8')
        
        assert '# Authorized Digital Sellers' in content
        assert 'google.com' in content
        assert 'pub-4242043087380150' in content
        assert 'DIRECT' in content
        assert 'f08c47fec0942fa0' in content


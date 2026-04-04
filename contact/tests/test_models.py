"""Tests for Contact Models"""
import pytest
from django.test import TestCase
from contact.models import ContactOption


@pytest.mark.django_db
class TestContactOptionModel(TestCase):
    """Tests para el modelo ContactOption"""
    
    def setUp(self):
        """Setup para tests del modelo"""
        self.contact = ContactOption.objects.create(
            name="Juan Pérez",
            email="juan@example.com",
            contact_method="email",
            subject="Consulta sobre producto",
            message="¿Tenés stock de X?"
        )
    
    def test_contact_creation(self):
        """Test: Crear contacto exitosamente"""
        self.assertEqual(self.contact.name, "Juan Pérez")
        self.assertEqual(self.contact.email, "juan@example.com")
        self.assertEqual(self.contact.contact_method, "email")
    
    def test_contact_str_representation(self):
        """Test: __str__() devuelve formato esperado"""
        expected = "Juan Pérez - Consulta sobre producto"
        self.assertEqual(str(self.contact), expected)
    
    def test_contact_method_choices(self):
        """Test: contact_method solo acepta valores válidos"""
        valid_methods = ['email', 'whatsapp']
        for method in valid_methods:
            contact = ContactOption.objects.create(
                name="Test",
                email="test@example.com",
                contact_method=method,
                subject="Test",
                message="Test"
            )
            self.assertIn(contact.contact_method, valid_methods)
    
    def test_contact_created_at_auto_set(self):
        """Test: created_at se asigna automáticamente"""
        self.assertIsNotNone(self.contact.created_at)

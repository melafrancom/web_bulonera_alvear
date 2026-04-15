"""
Tests para los filtros personalizados de templates.
"""
import pytest
from django.template import Context, Template
from django.test import TestCase
from web_bulonera.templatetags.custom_filters import add, multiply, slice_range, times


class TestAddFilter(TestCase):
    """Tests para el filtro add."""
    
    def test_add_integers(self):
        """Suma de dos enteros."""
        result = add(2, 3)
        self.assertEqual(result, 5.0)
    
    def test_add_floats(self):
        """Suma con valores float (strings)."""
        result = add(1, "-0.5")
        self.assertEqual(result, 0.5)
    
    def test_add_negative_float(self):
        """Suma con float negativo."""
        result = add(5, "-0.9")
        self.assertAlmostEqual(result, 4.1, places=1)
    
    def test_add_invalid_arg_returns_value(self):
        """Con argumento inválido, retorna el valor original."""
        result = add(5, "invalid")
        self.assertEqual(result, 5)
    
    def test_add_with_queryset_returns_value(self):
        """Con QuerySet como argumento, retorna el valor original sin explotar."""
        from django.db.models import QuerySet
        from store.models import Product
        
        # Crear un QuerySet vacío
        qs = Product.objects.none()
        result = add(5, qs)
        self.assertEqual(result, 5)


class TestMultiplyFilter(TestCase):
    """Tests para el filtro multiply."""
    
    def test_multiply_integers(self):
        """Multiplicación de dos enteros."""
        result = multiply(3, 4)
        self.assertEqual(result, 12.0)
    
    def test_multiply_floats(self):
        """Multiplicación con floats."""
        result = multiply(2.5, 4)
        self.assertEqual(result, 10.0)
    
    def test_multiply_invalid_returns_value(self):
        """Con argumento inválido, retorna el valor original."""
        result = multiply(3, "abc")
        self.assertEqual(result, 3)


class TestSliceRangeFilter(TestCase):
    """Tests para el filtro slice_range."""
    
    def test_slice_range_valid(self):
        """Slice válido de una lista."""
        test_list = [1, 2, 3, 4, 5]
        result = slice_range(test_list, "1,3")
        self.assertEqual(list(result), [2, 3])
    
    def test_slice_range_invalid_returns_original(self):
        """Con argumentos inválidos, retorna la lista original."""
        test_list = [1, 2, 3, 4, 5]
        result = slice_range(test_list, "invalid")
        self.assertEqual(result, test_list)


class TestTimesFilter(TestCase):
    """Tests para el filtro times."""
    
    def test_times_creates_range(self):
        """Convierte un entero en un rango."""
        result = times(5)
        self.assertEqual(list(result), [0, 1, 2, 3, 4])
    
    def test_times_zero(self):
        """Con cero, retorna rango vacío."""
        result = times(0)
        self.assertEqual(list(result), [])


class TestFiltersInTemplate(TestCase):
    """Tests de integración de filtros en templates."""
    
    def test_add_in_template(self):
        """Test del filtro add usado en template."""
        template = Template("{% load custom_filters %}{{ value|add:arg }}")
        context = Context({"value": 5, "arg": 3})
        result = template.render(context)
        # El resultado puede ser "8.0" o "8,0" dependiendo de la localización
        self.assertIn(result, ["8.0", "8,0"])
    
    def test_add_with_negative_float_in_template(self):
        """Test del filtro add con float negativo en template."""
        template = Template("{% load custom_filters %}{{ value|add:'-0.5' }}")
        context = Context({"value": 3})
        result = template.render(context)
        # El resultado puede ser "2.5" o "2,5" dependiendo de la localización
        self.assertIn(result, ["2.5", "2,5"])
    
    def test_multiply_in_template(self):
        """Test del filtro multiply usado en template."""
        template = Template("{% load custom_filters %}{{ value|multiply:arg }}")
        context = Context({"value": 4, "arg": 3})
        result = template.render(context)
        # El resultado puede ser "12.0" o "12,0" dependiendo de la localización
        self.assertIn(result, ["12.0", "12,0"])

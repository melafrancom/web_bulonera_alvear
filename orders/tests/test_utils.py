"""
Tests unitarios para orders/utils.py (Validaciones fiscales y comerciales)
"""
import pytest
from orders.utils import validate_cuit, format_cuit, validate_dni


class TestCuitValidation:
    """Pruebas de algoritmo Módulo 11 para CUIT argentino"""

    def test_valid_cuit_afip(self):
        # CUIT oficial de AFIP / ARCA
        assert validate_cuit('33-69345023-9') is True
        assert validate_cuit('33693450239') is True

    def test_valid_cuit_person(self):
        # CUIT válido persona física
        # 20-22222222-3 -> 2*5+0*4 + 2*3+2*2+2*7+2*6+2*5+2*4+2*3+2*2 = 10 + 6+4+14+12+10+8+6+4 = 74. 74 % 11 = 8. 11-8 = 3.
        assert validate_cuit('20-22222222-3') is True
        assert validate_cuit('20222222223') is True

    def test_invalid_cuit_wrong_checksum(self):
        # Mismo CUIT pero con dígito verificador alterado
        assert validate_cuit('33-69345023-5') is False
        assert validate_cuit('20-22222222-0') is False

    def test_invalid_cuit_wrong_prefix(self):
        # Prefijo no existente en Argentina (ej. 99)
        assert validate_cuit('99-12345678-1') is False

    def test_invalid_cuit_length_or_format(self):
        assert validate_cuit('') is False
        assert validate_cuit(None) is False
        assert validate_cuit('12345678') is False
        assert validate_cuit('abcdefghijk') is False

    def test_format_cuit(self):
        assert format_cuit('33693450239') == '33-69345023-9'
        assert format_cuit('33-69345023-9') == '33-69345023-9'
        assert format_cuit('123') == '123'
        assert format_cuit('') == ''


class TestDniValidation:
    """Pruebas de formato para DNI"""

    def test_valid_dni(self):
        assert validate_dni('12345678') is True
        assert validate_dni('12.345.678') is True
        assert validate_dni('7654321') is True

    def test_invalid_dni(self):
        assert validate_dni('12345') is False
        assert validate_dni('1234567890') is False
        assert validate_dni('') is False
        assert validate_dni(None) is False

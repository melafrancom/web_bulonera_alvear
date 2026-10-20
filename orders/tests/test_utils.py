"""
Tests unitarios para orders/utils.py (Validaciones fiscales y comerciales)
Cubre contratos estrictos ASCII, rechazo de controles, dígitos Unicode,
separadores mal ubicados y algoritmo Módulo 11 de ARCA.
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
        # 20-22222222-3 -> ponderado Módulo 11
        assert validate_cuit('20-22222222-3') is True
        assert validate_cuit('20222222223') is True

    def test_valid_cuit_with_outer_spaces(self):
        # Espacio simple exterior permitido (copy-paste benigno)
        assert validate_cuit(' 33-69345023-9 ') is True
        assert validate_cuit(' 33693450239') is True

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

    def test_invalid_cuit_unicode_digits(self):
        # Rechaza dígitos Unicode arábigos o fullwidth
        assert validate_cuit('٣٣٦٩٣٤٥٠٢٣٩') is False
        assert validate_cuit('20-22222222-３') is False
        assert validate_cuit('２０-２２２２２２２２-３') is False

    def test_invalid_cuit_control_characters(self):
        # Rechaza terminantemente saltos de línea y tabulaciones
        assert validate_cuit('33-69345023-9\n') is False
        assert validate_cuit('\r\n33693450239') is False
        assert validate_cuit('33-69345023-9\r') is False
        assert validate_cuit('\t33-69345023-9') is False

    def test_invalid_cuit_misplaced_or_repeated_separators(self):
        # Rechaza dobles guiones, guiones en posiciones erróneas, puntos o espacios interiores
        assert validate_cuit('33--69345023-9') is False
        assert validate_cuit('3-369345023-9') is False
        assert validate_cuit('33-6934-50239') is False
        assert validate_cuit('-33693450239') is False
        assert validate_cuit('33693450239-') is False
        assert validate_cuit('33.693.450.239') is False
        assert validate_cuit('33 69345023 9') is False

    def test_format_cuit_valid(self):
        assert format_cuit('33693450239') == '33-69345023-9'
        assert format_cuit('33-69345023-9') == '33-69345023-9'
        assert format_cuit(' 33693450239 ') == '33-69345023-9'

    def test_format_cuit_invalid_returns_empty(self):
        # REGLA: No convierte silenciosamente entradas corruptas
        assert format_cuit('123') == ''
        assert format_cuit('') == ''
        assert format_cuit(None) == ''
        assert format_cuit('33-69345023-5') == ''
        assert format_cuit('malformed-33693450239') == ''


class TestDniValidation:
    """Pruebas de formato para DNI"""

    def test_valid_dni(self):
        assert validate_dni('12345678') is True
        assert validate_dni('12.345.678') is True
        assert validate_dni('7654321') is True
        assert validate_dni('7.654.321') is True
        assert validate_dni(' 12345678 ') is True

    def test_invalid_dni_length_or_type(self):
        assert validate_dni('12345') is False
        assert validate_dni('1234567890') is False
        assert validate_dni('') is False
        assert validate_dni(None) is False
        assert validate_dni('abcdefg') is False

    def test_invalid_dni_unicode_digits(self):
        assert validate_dni('١٢٣٤٥٦٧٨') is False
        assert validate_dni('１２３４５６７８') is False

    def test_invalid_dni_control_characters(self):
        assert validate_dni('12345678\n') is False
        assert validate_dni('\r12.345.678') is False
        assert validate_dni('\t12345678') is False

    def test_invalid_dni_misplaced_or_repeated_separators(self):
        assert validate_dni('12..345.678') is False
        assert validate_dni('123.456.78') is False
        assert validate_dni('1.2345.678') is False
        assert validate_dni('12-345-678') is False
        assert validate_dni('12 345 678') is False

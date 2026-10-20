"""
Orders Utilities

Funciones de utilidad y validadores comerciales/fiscales para órdenes y checkout.
Aplica contrato estricto ASCII, algoritmo Módulo 11 oficial de ARCA y rechazo
explícito de caracteres de control, caracteres Unicode y separadores mal ubicados.
"""
import re
from typing import Optional

# Regex canónicas exactas limitadas a caracteres ASCII [0-9]
CUIT_ASCII_REGEX = re.compile(r'^(?:[0-9]{11}|[0-9]{2}-[0-9]{8}-[0-9]{1})$')
DNI_ASCII_REGEX = re.compile(r'^(?:[0-9]{7,8}|[0-9]{1,2}\.[0-9]{3}\.[0-9]{3})$')


def validate_cuit(cuit: Optional[str]) -> bool:
    """
    Valida un número de CUIT/CUIL argentino mediante validación estructural ASCII estricta
    seguida del algoritmo Módulo 11 oficial de ARCA.

    # REGLA: Contrato estricto
    - Rechaza caracteres no ASCII (e.g. dígitos Unicode arábigos o fullwidth).
    - Rechaza caracteres de control (\\n, \\r, \\t, etc.).
    - Tolera únicamente espacio simple ASCII exterior (' ').
    - Formato exacto: 11 dígitos continuos o con guiones canónicos XX-XXXXXXXX-X.
    - Dígito verificador coincide con el cálculo ponderado Módulo 11.
    """
    if not cuit or not isinstance(cuit, str):
        return False

    # 1. Comprobación estricta de juego de caracteres ASCII
    if not cuit.isascii():
        return False

    # 2. Rechazo terminante de controles (saltos de línea, retornos, tabulaciones)
    if any(c in '\r\n\t' or ord(c) < 32 or ord(c) == 127 for c in cuit):
        return False

    # 3. Saneamiento exclusivo de espacios simples ASCII exteriores (copy-paste benigno)
    cuit_clean = cuit.strip(' ')

    # 4. Validación de sintaxis estructural con fullmatch
    if not CUIT_ASCII_REGEX.fullmatch(cuit_clean):
        return False

    # 5. Extracción segura de dígitos ASCII
    digits = [int(c) for c in cuit_clean if '0' <= c <= '9']
    if len(digits) != 11:
        return False

    # 6. Prefijos homologados en Argentina
    prefix = digits[0] * 10 + digits[1]
    if prefix not in (20, 23, 24, 27, 30, 33, 34):
        return False

    # 7. Algoritmo Módulo 11 ponderado
    multipliers = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    total = sum(d * m for d, m in zip(digits[:10], multipliers))
    mod = total % 11
    diff = 11 - mod

    if diff == 11:
        expected_check = 0
    elif diff == 10:
        expected_check = 9
    else:
        expected_check = diff

    return digits[10] == expected_check


def format_cuit(cuit: Optional[str]) -> str:
    """
    Formatea un string de CUIT a la convención canónica XX-XXXXXXXX-X únicamente si es válido.
    Si la entrada no cumple el contrato estricto, retorna cadena vacía para evitar
    conversiones silenciosas de datos malformados.
    """
    if not validate_cuit(cuit):
        return ""
    clean = ''.join(c for c in str(cuit) if '0' <= c <= '9')
    return f"{clean[:2]}-{clean[2:10]}-{clean[10]}"


def validate_dni(dni: Optional[str]) -> bool:
    """
    Valida un número de DNI argentino básico (7 u 8 dígitos numéricos ASCII).
    Acepta formato continuo o canónico con puntos (ej. 28123456 o 28.123.456).
    Rechaza controles, dígitos Unicode, separadores dobles o mal ubicados.
    """
    if not dni or not isinstance(dni, str):
        return False

    if not dni.isascii():
        return False

    if any(c in '\r\n\t' or ord(c) < 32 or ord(c) == 127 for c in dni):
        return False

    dni_clean = dni.strip(' ')
    return bool(DNI_ASCII_REGEX.fullmatch(dni_clean))


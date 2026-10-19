"""
Orders Utilities

Funciones de utilidad y validadores comerciales/fiscales para órdenes y checkout.
"""
import re
from typing import Optional


def validate_cuit(cuit: Optional[str]) -> bool:
    """
    Valida un número de CUIT/CUIL argentino mediante el algoritmo Módulo 11 oficial de AFIP/ARCA.

    Reglas:
    - Longitud exacta de 11 dígitos numéricos.
    - Prefijos válidos: 20, 23, 24, 27, 30, 33, 34.
    - Factores de ponderación: [5, 4, 3, 2, 7, 6, 5, 4, 3, 2].
    - Dígito verificador coincide con el cálculo ponderado.
    """
    if not cuit:
        return False

    digits = [int(d) for d in str(cuit) if d.isdigit()]
    if len(digits) != 11:
        return False

    prefix = digits[0] * 10 + digits[1]
    if prefix not in (20, 23, 24, 27, 30, 33, 34):
        return False

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
    Formatea un string de CUIT a la convención canónica XX-XXXXXXXX-X.
    Si no tiene 11 dígitos, retorna el valor original saneado.
    """
    if not cuit:
        return ""
    clean = re.sub(r'\D', '', str(cuit))
    if len(clean) == 11:
        return f"{clean[:2]}-{clean[2:10]}-{clean[10]}"
    return clean


def validate_dni(dni: Optional[str]) -> bool:
    """
    Valida un número de DNI argentino básico (7 u 8 dígitos numéricos).
    """
    if not dni:
        return False
    clean = re.sub(r'\D', '', str(dni))
    return len(clean) in (7, 8)

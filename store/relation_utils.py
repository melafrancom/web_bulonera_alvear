"""
Utilidades puras de normalización técnica para relaciones de productos.

Separadas en módulo propio para evitar importaciones circulares entre
`store.models`, `store.services` y migraciones de datos.
"""
import re
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

from django.utils.text import slugify

# Mapa de compatibilidad entre familias canónicas de rosca.
# POR QUÉ: En el catálogo real conviven denominaciones genéricas ('Milimétrica',
# 'Pulgada') junto a subtipos específicos ('MA', 'MB', 'UNC', 'UNF').
COMPATIBLE_THREAD_FAMILIES = {
    'metric': {'metric', 'ma', 'mb'},
    'ma': {'ma', 'metric'},
    'mb': {'mb', 'metric'},
    'inch': {'inch', 'unc', 'unf'},
    'unc': {'unc', 'inch'},
    'unf': {'unf', 'inch'},
}

_PAREN_RE = re.compile(r'\s*\([^)]*\)')
_WHITESPACE_RE = re.compile(r'\s+')
_METRIC_PITCH_RE = re.compile(
    r'^(.+?)\s*[x×]\s*(?:p\s*(\d+(?:[.,]\d+)?)|(\d+[.,]\d+))$',
    re.IGNORECASE,
)
_TPI_PITCH_RE = re.compile(r'^(.+?)\s*[x×]\s*(\d+)\s*h$', re.IGNORECASE)
_HOSE_DIM_RE = re.compile(r'^(\d+)\s*[x×]\s*(\d+)$', re.IGNORECASE)
_M_PREFIX_RE = re.compile(r'^m\s*', re.IGNORECASE)
_MM_SUFFIX_RE = re.compile(r'\s*mm$', re.IGNORECASE)
_MIXED_FRACTION_RE = re.compile(r'^(\d+)[\s-]+(\d+/\d+)$')
_SLASH_SPACES_RE = re.compile(r'\s*/\s*')
_THREAD_EXPLICIT_P_RE = re.compile(r'\bp\s*(\d+(?:[.,]\d+)?)\b', re.IGNORECASE)
_THREAD_ONLY_DECIMAL_RE = re.compile(r'^\s*(\d+[.,]\d+)\s*$')
_THREAD_TPI_RE = re.compile(r'\b(\d+)\s*h\b', re.IGNORECASE)
_MA_TOKEN_RE = re.compile(r'(?:^|\b)ma(?:\b|\s*\()', re.IGNORECASE)
_MB_TOKEN_RE = re.compile(r'(?:^|\b)mb(?:\b|\s*\()', re.IGNORECASE)


def normalize_pitch_number(raw_num: Optional[str]) -> str:
    """
    Normaliza un número decimal de paso métrico eliminando ceros finales.

    Ejemplos: '1.0' -> '1', '1.50' -> '1.5', '2,00' -> '2', '1.25' -> '1.25'.
    """
    if not raw_num:
        return ''
    cleaned = str(raw_num).strip().replace(',', '.')
    try:
        dec = Decimal(cleaned).normalize()
    except InvalidOperation:
        return cleaned[:20]

    text = format(dec, 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text[:20]


def _normalize_diameter_base(raw_base: str) -> str:
    """Normaliza la base de un diámetro (sin equivalencias en paréntesis ni paso)."""
    base = raw_base.strip().lower()
    base = _M_PREFIX_RE.sub('', base)
    base = _MM_SUFFIX_RE.sub('', base)
    base = _SLASH_SPACES_RE.sub('/', base)
    base = _MIXED_FRACTION_RE.sub(r'\1.\2', base)
    base = _WHITESPACE_RE.sub(' ', base).strip()
    return base[:50]


def parse_diameter_and_pitch(raw: Optional[str]) -> Tuple[str, str]:
    """
    Extrae (diameter_nominal, thread_pitch) calibrado sobre los patrones del catálogo.

    QUÉ: Separa diámetro nominal y paso embebido ('6 x P 1.0' -> ('6', '1'),
    '1/2 x 12H' -> ('1/2', '12h')), limpia paréntesis ('1/2 (12.7mm)' -> ('1/2', ''))
    y preserva medidas compuestas de mangueras ('8 x 12' -> ('8x12', '')).
    """
    if not raw:
        return '', ''

    cleaned = str(raw).strip()
    if not cleaned:
        return '', ''

    for quote_char in ('"', '”', '″'):
        cleaned = cleaned.replace(quote_char, '')
    cleaned = _WHITESPACE_RE.sub(' ', cleaned).strip()
    cleaned = _PAREN_RE.sub('', cleaned).strip()
    if not cleaned:
        return '', ''

    metric_match = _METRIC_PITCH_RE.match(cleaned)
    if metric_match:
        raw_base = metric_match.group(1)
        raw_pitch = metric_match.group(2) or metric_match.group(3)
        return _normalize_diameter_base(raw_base), normalize_pitch_number(raw_pitch)

    tpi_match = _TPI_PITCH_RE.match(cleaned)
    if tpi_match:
        raw_base = tpi_match.group(1)
        tpi_num = tpi_match.group(2)
        return _normalize_diameter_base(raw_base), f"{tpi_num}h"[:20]

    # REGLA: Dos enteros separados por 'x' sin 'P', decimal ni 'H' representan
    # medidas interior x exterior de mangueras ('5 x 8', '8 x 12'), no paso de rosca.
    hose_match = _HOSE_DIM_RE.match(cleaned)
    if hose_match:
        return f"{hose_match.group(1)}x{hose_match.group(2)}"[:50], ''

    return _normalize_diameter_base(cleaned), ''


def normalize_thread_format(raw: Optional[str]) -> Tuple[str, str]:
    """
    Extrae (thread_family, extracted_pitch) a partir de thread_formats o thread_formats_relation.

    QUÉ: Mapea sinónimos reales del catálogo ('USS / UNC(rosca gruesa)', 'UNC/BSW' -> 'unc';
    'MA (rosca gruesa)' -> 'ma') y extrae pasos explícitos ('P 1.0' -> ('', '1')).
    """
    if not raw:
        return '', ''

    cleaned = _WHITESPACE_RE.sub(' ', str(raw).strip())
    if not cleaned:
        return '', ''

    extracted_pitch = ''
    p_match = _THREAD_EXPLICIT_P_RE.search(cleaned)
    if p_match:
        extracted_pitch = normalize_pitch_number(p_match.group(1))
    else:
        dec_match = _THREAD_ONLY_DECIMAL_RE.match(cleaned)
        if dec_match:
            extracted_pitch = normalize_pitch_number(dec_match.group(1))
        else:
            tpi_match = _THREAD_TPI_RE.search(cleaned)
            if tpi_match:
                extracted_pitch = f"{tpi_match.group(1)}h"[:20]

    # Si el texto remanente tras quitar el paso queda vacío, el input era solo un paso.
    without_pitch = _THREAD_EXPLICIT_P_RE.sub('', cleaned)
    without_pitch = _THREAD_TPI_RE.sub('', without_pitch)
    without_pitch = _THREAD_ONLY_DECIMAL_RE.sub('', without_pitch)
    without_pitch = without_pitch.strip(' -–—/(),.')
    if not without_pitch:
        return '', extracted_pitch

    lower_val = (
        without_pitch.lower()
        .replace('á', 'a')
        .replace('é', 'e')
        .replace('í', 'i')
        .replace('ó', 'o')
        .replace('ú', 'u')
    )

    if any(tok in lower_val for tok in ('unc', 'uss', 'bsw')):
        family = 'unc'
    elif 'unf' in lower_val:
        family = 'unf'
    elif 'pulgada' in lower_val:
        family = 'inch'
    elif _MA_TOKEN_RE.search(lower_val):
        family = 'ma'
    elif _MB_TOKEN_RE.search(lower_val):
        family = 'mb'
    elif 'milim' in lower_val or 'metri' in lower_val:
        family = 'metric'
    else:
        family = slugify(without_pitch)[:50]

    return family, extracted_pitch

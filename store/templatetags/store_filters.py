from django import template
import os

register = template.Library()

@register.filter
def basename(value):
    """Obtiene el nombre base del archivo sin extensión"""
    if not value:
        return ''
    filename = os.path.basename(value)
    return os.path.splitext(filename)[0]

@register.filter
def times(number):
    """Crea un rango de números para iterar"""
    try:
        return range(int(number))
    except (ValueError, TypeError):
        return range(0)

@register.filter
def elided_page_range(number, paginator):
    """
    Retorna un rango de páginas elidido para catálogos muy grandes.
    Delegación a paginator.get_elided_page_range() de Django.
    
    Ejemplo: con on_each_side=1, on_ends=1
    - Página 7 de 58: [1] [...] [6] [7] [8] [...] [58]
    
    Args:
        number: número de página actual
        paginator: objeto Paginator de Django
    """
    try:
        # on_each_side: cuántas páginas mostrar a los lados de la actual
        # on_ends: cuántas páginas mostrar al principio y al final
        return paginator.get_elided_page_range(number, on_each_side=1, on_ends=1)
    except Exception:
        # Fallback: retornar rango completo si falla elisión
        return paginator.page_range


@register.filter
def argentina_currency(value):
    """
    Formatea un valor numérico como moneda argentina: $1.234,56
    (punto para miles, coma para decimales)
    
    Sin dependencia de locale, garantizado funciona en cualquier OS.
    
    Ejemplos:
    - 1234.56 → $1.234,56
    - 1000 → $1.000,00
    - 100 → $100,00
    - 1000000.99 → $1.000.000,99
    """
    try:
        num = float(value)
    except (ValueError, TypeError):
        return str(value)
    
    # Paso 1: Formatear con 2 decimales (sin separadores)
    formatted = f"{num:.2f}"  # Ej: "1234.56"
    
    # Paso 2: Separar integer y decimal
    integer_str, decimal_str = formatted.split('.')
    
    # Paso 3: Insertar puntos cada 3 dígitos desde derecha a izquierda
    # Ej: "1000000" → "1.000.000"
    integer_with_thousands = ""
    for i, digit in enumerate(reversed(integer_str)):
        if i > 0 and i % 3 == 0:
            integer_with_thousands = "." + integer_with_thousands
        integer_with_thousands = digit + integer_with_thousands
    
    # Paso 4: Armar resultado final con formato argentino
    return f"${integer_with_thousands},{decimal_str}"
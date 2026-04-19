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

# ... existing code ... 
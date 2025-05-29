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

# ... existing code ... 
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary"""
    return dictionary.get(key)

@register.filter
def multiply(value, arg):
    """Multiply a value by an argument"""
    return int(value) * int(arg)

@register.filter
def slice_range(value, args):
    """
    Returns a slice of the list using start and end parameters.
    Usage: {{ list|slice_range:start,end }}
    """
    try:
        start, end = map(int, args.split(','))
        return value[start:end]
    except (ValueError, TypeError):
        return value

@register.filter
def times(value):
    """
    Convierte un entero en un rango para iterar en templates
    """
    return range(value)

@register.filter
def add(value, arg):
    """
    Suma un valor y un argumento
    """
    return int(value) + int(arg)

@register.filter
def make_list(value):
    """
    Convierte una cadena en una lista
    """
    return list(value)
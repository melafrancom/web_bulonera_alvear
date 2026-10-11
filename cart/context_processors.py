"""
Cart Context Processors

Provee datos del carrito para templates.
"""
from cart.services import CartService


def counter(request):
    """
    Context processor que provee el conteo de items del carrito.
    
    Uso en templates: {{ cart_count }}
    """
    # REGLA: Acceso defensivo a session y user en caso de errores tempranos (DisallowedHost, etc.)
    if not hasattr(request, 'session'):
        return dict(cart_count=0)
    user = request.user if getattr(request, 'user', None) and request.user.is_authenticated else None
    cart_count = CartService.get_cart_count(request, user)
    
    return dict(cart_count=cart_count)
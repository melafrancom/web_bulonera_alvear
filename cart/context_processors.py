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
    user = request.user if request.user.is_authenticated else None
    cart_count = CartService.get_cart_count(request, user)
    
    return dict(cart_count=cart_count)
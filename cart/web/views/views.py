"""Cart Web Views"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse

import logging

from cart.services import CartService
from cart.models import CartItem
from store.models import Product, Variation

logger = logging.getLogger(__name__)


def cart_view(request):
    """
    Vista del carrito de compras.
    Muestra todos los items del carrito con sus totales.
    """
    user = request.user if request.user.is_authenticated else None
    cart_items = CartService.get_cart_items(request, user)
    cart_data = CartService.calculate_cart_totals(cart_items)
    
    # Breadcrumb
    breadcrumb_items = [
        {'name': 'Inicio', 'url': '/'},
        {'name': 'Carrito', 'url': None}
    ]
    
    context = {
        'cart_items': cart_data['items'],
        'total': cart_data['total'],
        'quantity': cart_data['quantity'],
        'breadcrumb_items': breadcrumb_items,
    }
    
    return render(request, 'cart/cart.html', context)


def add_cart(request, product_id):
    """
    Agrega un producto al carrito.
    Soporta tanto usuarios autenticados como anónimos.
    """
    try:
        product = get_object_or_404(Product, id=product_id)
    except Exception:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'message': 'Producto no encontrado'
            }, status=404)
        return redirect('store:store')
    
    # Obtener cantidad
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
    else:
        quantity = int(request.GET.get('qty', 1))
    
    # Obtener variaciones del POST
    variations = []
    if request.method == 'POST':
        for key in request.POST:
            value = request.POST[key]
            try:
                variation = Variation.objects.get(
                    product=product,
                    variation_category__iexact=key,
                    variation_value__iexact=value
                )
                variations.append(variation)
            except Variation.DoesNotExist:
                pass
            except Exception as e:
                logger.error(f"Error fetching variation {key}={value}: {e}")
    
    # Agregar al carrito usando el servicio
    try:
        user = request.user if request.user.is_authenticated else None
        CartService.add_to_cart(
            request=request,
            product=product,
            quantity=quantity,
            variations=variations,
            user=user
        )
        
        # Responder según el tipo de request
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        else:
            # Redirigir a la página anterior
            referer_url = request.META.get('HTTP_REFERER')
            if referer_url:
                return HttpResponseRedirect(referer_url)
            else:
                return redirect('store:store')
                
    except ValueError as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
        return redirect('cart:cart')
    except Exception as e:
        logger.error(f"Error adding to cart: {e}")
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'error',
                'message': 'Error al agregar al carrito'
            }, status=500)
        return redirect('cart:cart')


def remove_cart(request, product_id, cart_item_id):
    """
    Decrementa la cantidad de un item del carrito.
    Si la cantidad llega a 0, elimina el item.
    """
    user = request.user if request.user.is_authenticated else None
    CartService.remove_from_cart(
        request=request,
        product_id=product_id,
        cart_item_id=cart_item_id,
        user=user,
        remove_completely=False
    )
    return redirect('cart:cart')


def remove_cart_item(request, product_id, cart_item_id):
    """
    Elimina completamente un item del carrito.
    """
    user = request.user if request.user.is_authenticated else None
    CartService.remove_from_cart(
        request=request,
        product_id=product_id,
        cart_item_id=cart_item_id,
        user=user,
        remove_completely=True
    )
    return redirect('cart:cart')


def get_cart_data(request):
    """
    Endpoint AJAX para obtener datos del carrito en formato JSON.
    Usado para actualizar el contador del carrito dinámicamente.
    """
    user = request.user if request.user.is_authenticated else None
    cart_items = CartService.get_cart_items(request, user)
    cart_data = CartService.calculate_cart_totals(cart_items)
    
    # Construir datos de items para JSON
    cart_items_data = []
    for item in cart_data['items']:
        cart_items_data.append({
            'id': item.id,
            'name': item.product.name,
            'price': float(item.sub_total),
            'quantity': item.quantity,
            'image': item.product.image_url,
        })
    
    return JsonResponse({
        'cart_count': cart_data['quantity'],
        'cart_total': float(cart_data['total']),
        'cart_items': cart_items_data
    })


@login_required(login_url='login')
def checkout(request):
    """
    Vista de checkout (requiere autenticación).
    Muestra el resumen del carrito antes de proceder al pago.
    """
    user = request.user
    cart_items = CartService.get_cart_items(request, user)
    cart_data = CartService.calculate_cart_totals(cart_items)
    
    # Breadcrumb
    breadcrumb_items = [
        {'name': 'Inicio', 'url': '/'},
        {'name': 'Carrito', 'url': '/cart/'},
        {'name': 'Checkout', 'url': None}
    ]
    
    context = {
        'cart_items': cart_data['items'],
        'total': cart_data['total'],
        'quantity': cart_data['quantity'],
        'breadcrumb_items': breadcrumb_items,
    }
    
    return render(request, 'cart/checkout.html', context)

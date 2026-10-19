"""Cart Web Views"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist

import logging

from cart.services import CartService
from cart.models import CartItem
from store.models import Product, Variation
from orders.web.forms import OrderForm

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


@require_POST
def add_cart(request, product_id):
    """
    Agrega un producto al carrito.
    Soporta tanto usuarios autenticados como anónimos.
    Requiere método POST con protección CSRF obligatoria.
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
    
    # SEC-108: Validar cantidad contra DoS e input inválido mediante CartService
    raw_quantity = request.POST.get('quantity') or request.POST.get('qty')
    quantity = CartService.clamp_quantity(raw_quantity, default=1, min_val=1, max_val=1000)
    
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
        fb_event_id = request.POST.get('fb_event_id')
        if fb_event_id:
            from tracking.services import MetaCapiService
            MetaCapiService.enqueue_add_to_cart(
                request=request,
                product=product,
                quantity=quantity,
                event_id=fb_event_id
            )

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        else:
            # SEC-103: Redirigir a la página anterior de forma segura (prevención Open Redirect)
            referer_url = request.META.get('HTTP_REFERER')
            if referer_url and url_has_allowed_host_and_scheme(
                url=referer_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return HttpResponseRedirect(referer_url)
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


@require_POST
def remove_cart(request, product_id, cart_item_id):
    """
    Decrementa la cantidad de un item del carrito.
    Si la cantidad llega a 0, elimina el item.
    Requiere método POST con protección CSRF obligatoria.
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


@require_POST
def update_cart_quantity(request, cart_item_id: int):
    """
    Actualiza la cantidad de un ítem del carrito.
    Soporta AJAX (retorna JSON para Alpine.js con cadenas decimales) y POST tradicional (302).
    """
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json'
    user = request.user if request.user.is_authenticated else None
    cart_id = CartService.get_or_create_cart_id(request) if not user else None
    
    # 1. Validación estricta de entrada (No convertir silenciosamente inválidos en 1)
    raw_quantity = request.POST.get('quantity') or request.POST.get('qty')
    if raw_quantity is None or str(raw_quantity).strip() == '':
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'La cantidad es requerida.'}, status=400)
        messages.error(request, 'La cantidad es requerida.')
        return redirect('cart:cart')

    try:
        quantity = int(raw_quantity)
    except (ValueError, TypeError):
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'La cantidad debe ser un número entero válido.'}, status=400)
        messages.error(request, 'La cantidad debe ser un número entero válido.')
        return redirect('cart:cart')

    # 2. Ejecución en Servicio
    try:
        updated_item = CartService.update_quantity(
            cart_item_id=cart_item_id,
            quantity=quantity,
            user=user,
            cart_id=cart_id
        )
        
        # 3. Recalcular totales frescos
        cart_items = CartService.get_cart_items(request, user)
        cart_data = CartService.calculate_cart_totals(cart_items)
        items_list = list(cart_data['items'])
        item_count = len(items_list)
        total_units = cart_data['quantity']

        if is_ajax:
            return JsonResponse({
                'status': 'success',
                'item': {
                    'id': updated_item.id,
                    'quantity': updated_item.quantity,
                    'unit_price': f"{updated_item.purchase_price:.2f}",
                    'subtotal': f"{updated_item.sub_total:.2f}",
                },
                'cart': {
                    'total': f"{cart_data['total']:.2f}",
                    'quantity': total_units,
                    'item_count': item_count,
                    'is_empty': item_count == 0,
                }
            })

        return redirect('cart:cart')

    except ValueError as val_err:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': str(val_err)}, status=400)
        messages.error(request, str(val_err))
        return redirect('cart:cart')

    except ObjectDoesNotExist:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'El producto no fue encontrado en tu carrito.'}, status=404)
        messages.error(request, 'El producto no fue encontrado en tu carrito.')
        return redirect('cart:cart')

    except Exception as err:
        logger.error(f"Error actualizando cantidad en cart_item {cart_item_id}: {err}", exc_info=True)
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'Ocurrió un error al actualizar el carrito.'}, status=500)
        messages.error(request, 'Ocurrió un error al actualizar el carrito.')
        return redirect('cart:cart')


@require_POST
def remove_cart_item(request, product_id, cart_item_id):
    """
    Elimina completamente un item del carrito.
    Soporta AJAX (retorna totales y flag is_empty) y POST tradicional (302).
    """
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json'
    user = request.user if request.user.is_authenticated else None
    
    success = CartService.remove_from_cart(
        request=request,
        product_id=product_id,
        cart_item_id=cart_item_id,
        user=user,
        remove_completely=True
    )

    if is_ajax:
        cart_items = CartService.get_cart_items(request, user)
        cart_data = CartService.calculate_cart_totals(cart_items)
        items_list = list(cart_data['items'])
        item_count = len(items_list)

        return JsonResponse({
            'status': 'deleted' if success else 'error',
            'item_id': cart_item_id,
            'cart': {
                'total': f"{cart_data['total']:.2f}",
                'quantity': cart_data['quantity'],
                'item_count': item_count,
                'is_empty': item_count == 0,
            }
        })

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


@login_required(login_url='account:login')
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
    
    # Pre-populate form initial data
    initial_data = {
        'first_name': user.first_name,
        'last_name': user.last_name,
        'email': user.email,
        'phone': getattr(user, 'phone', ''),
    }
    form = OrderForm(initial=initial_data)
    
    context = {
        'form': form,
        'cart_items': cart_data['items'],
        'total': cart_data['total'],
        'quantity': cart_data['quantity'],
        'breadcrumb_items': breadcrumb_items,
    }
    
    return render(request, 'cart/checkout.html', context)

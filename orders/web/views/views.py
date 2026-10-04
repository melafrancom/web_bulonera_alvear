"""Orders Web Views"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse
import json
import logging
from django.conf import settings

from orders.models import Order, OrderProduct
from orders.web.forms import OrderForm
from orders.services import (
    OrderService,
    PaymentService,
    CheckoutService,
    WhatsAppService
)
from tracking.services import MetaCapiService
from cart.models import CartItem

logger = logging.getLogger(__name__)


@login_required(login_url='account:login')
def place_order(request):
    """
    Vista para crear una orden desde el carrito.
    Muestra el formulario de checkout y procesa la creación de la orden.
    """
    current_user = request.user
    cart_items = CartItem.objects.filter(user=current_user, is_active=True)
    
    if not cart_items.exists():
        messages.warning(request, "Tu carrito está vacío")
        return redirect('store:store')
    
    # Calcular totales
    total = sum(item.sub_total for item in cart_items)
    quantity = sum(item.quantity for item in cart_items)
    
    if request.method == 'POST':
        form = OrderForm(request.POST)
        
        if form.is_valid():
            try:
                # Obtener IP
                ip_address = request.META.get('REMOTE_ADDR')
                
                # Crear orden usando el servicio
                order = CheckoutService.complete_checkout(
                    user=current_user,
                    form_data=form.cleaned_data,
                    ip_address=ip_address
                )
                
                # Redirigir a WhatsApp
                whatsapp_url = f'{reverse("orders:whatsapp_redirect")}?order_number={order.order_number}'
                logger.info(f"Orden {order.order_number} creada exitosamente")
                
                # Flag de conversión para Frontend (evita duplicados si el usuario recarga la página)
                request.session['ba_pending_purchase'] = order.order_number
                
                # Encolar Meta CAPI
                try:
                    MetaCapiService.enqueue_purchase(order, request)
                except Exception as capi_err:
                    logger.error(f"Error encolando CAPI: {capi_err}", exc_info=True)
                
                return redirect(whatsapp_url)
                
            except ValueError as e:
                logger.warning(f"Error validando orden: {e}")
                messages.error(request, str(e))
            except Exception as e:
                logger.error(f"Error creando orden: {e}", exc_info=True)
                messages.error(request, "Error al procesar la orden. Por favor intenta nuevamente.")
        else:
            logger.warning(f"Formulario inválido: {form.errors}")
            messages.error(request, "Por favor corrige los errores en el formulario")
    else:
        form = OrderForm()
    
    # Breadcrumb
    breadcrumb_items = [
        {'name': 'Inicio', 'url': '/'},
        {'name': 'Carrito', 'url': '/cart/'},
        {'name': 'Checkout', 'url': None}
    ]
    
    context = {
        'form': form,
        'cart_items': cart_items,
        'total': total,
        'quantity': quantity,
        'breadcrumb_items': breadcrumb_items,
    }
    
    return render(request, 'cart/checkout.html', context)


@login_required
@require_POST
def payments(request):
    """
    Vista para procesar pagos (POST JSON).
    Scaffold para futura integración de pasarela de pagos.
    """
    try:
        # Cargar datos del pago
        body = json.loads(request.body)
        
        # Validar campos requeridos
        required_fields = ['orderID', 'transID', 'payment_method', 'status']
        for field in required_fields:
            if field not in body:
                return JsonResponse({
                    'error': f'Falta el campo requerido: {field}'
                }, status=400)
        
        # Obtener orden
        order = get_object_or_404(
            Order,
            user=request.user,
            is_ordered=False,
            order_number=body['orderID']
        )
        
        # Procesar pago usando el servicio
        payment_data = {
            'payment_id': body['transID'],
            'payment_method': body['payment_method'],
            'status': body['status']
        }
        
        payment = PaymentService.process_payment(
            user=request.user,
            order=order,
            payment_data=payment_data
        )
        
        # Enviar email de confirmación
        CheckoutService.send_order_confirmation_email(order)
        
        # Generar link de WhatsApp
        whatsapp_link = WhatsAppService.generate_whatsapp_link(order)
        
        # Respuesta exitosa
        return JsonResponse({
            'status': 'success',
            'whatsapp_link': whatsapp_link,
            'order_number': order.order_number,
            'transID': payment.payment_id,
        })
        
    except ValueError as e:
        logger.warning(f"Error procesando pago: {e}")
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        logger.error(f"Error en payments: {e}", exc_info=True)
        return JsonResponse({'error': 'Error procesando el pago'}, status=500)


@login_required(login_url='account:login')
def order_complete(request, order_number):
    """
    Vista de confirmación de orden completada.
    Muestra el resumen de la orden y los productos.
    """
    order = get_object_or_404(Order, order_number=order_number, user=request.user)
    ordered_products = OrderProduct.objects.filter(order=order)
    
    # Calcular subtotal
    subtotal = sum(
        item.purchase_price * item.quantity 
        for item in ordered_products
    )
    
    # Obtener payment si existe
    payment = order.payment
    trans_id = payment.payment_id if payment else ""
    
    context = {
        'order': order,
        'ordered_products': ordered_products,
        'order_number': order.order_number,
        'transID': trans_id,
        'payment': payment,
        'subtotal': subtotal,
        'status': order.status
    }
    
    return render(request, 'orders/order_complete.html', context)


@login_required
def order_detail(request, order_number):
    """
    Vista de detalle de orden.
    Muestra información completa de la orden, productos y estado.
    """
    try:
        order = get_object_or_404(Order, order_number=order_number, user=request.user)
        ordered_products = OrderProduct.objects.filter(order=order)
        
        # Calcular subtotal
        subtotal = sum(
            item.purchase_price * item.quantity 
            for item in ordered_products
        )
        
        # Obtener payment si existe
        payment = order.payment
        trans_id = payment.payment_id if payment else ""
        
        # Breadcrumb
        breadcrumb_items = [
            {'name': 'Inicio', 'url': '/'},
            {'name': 'Mi Cuenta', 'url': reverse('account:dashboard')},
            {'name': 'Mis Órdenes', 'url': reverse('account:my_orders')},
            {'name': f'Orden {order_number}', 'url': None},
        ]
        
        context = {
            'order': order,
            'ordered_products': ordered_products,
            'order_number': order_number,
            'transID': trans_id,
            'payment': payment,
            'subtotal': subtotal,
            'status': order.status,
            'breadcrumb_items': breadcrumb_items,
        }
        
        return render(request, 'orders/order_detail.html', context)
        
    except Order.DoesNotExist:
        messages.error(request, "Orden no encontrada")
        return redirect('account:my_orders')


@login_required
def orders_index(request):
    """
    Vista raíz de órdenes.
    Redirige al dashboard de órdenes del usuario.
    """
    return redirect('account:my_orders')


@login_required
def whatsapp_redirect(request):
    """
    Vista de redirección a WhatsApp.
    Genera el mensaje y link de WhatsApp para la orden.
    """
    order_number = request.GET.get('order_number')
    if not order_number:
        messages.warning(request, "Orden no encontrada")
        return redirect('account:my_orders')
    
    try:
        order = Order.objects.get(
            order_number=order_number,
            user=request.user
        )
        
        # Generar link de WhatsApp
        whatsapp_link = WhatsAppService.generate_whatsapp_link(order)
        
        # Recuperar productos para el tracking de conversión
        ordered_products = OrderProduct.objects.filter(order=order)
        
        # Validar si es una compra nueva (evita disparar el tag nuevamente si recarga la página)
        pending_purchase_id = request.session.pop('ba_pending_purchase', None)
        is_new_purchase = (pending_purchase_id == order_number)
        
        # Payloads de Tracking (ADR-04 json_script)
        from tracking.services import TrackingPayloadService
        meta_payload = TrackingPayloadService.build_purchase_custom_data(order)
        ga4_payload = {
            'transaction_id': str(order.order_number),
            'value': float(order.order_total) if order.order_total else 0.0,
            'currency': getattr(settings, 'CURRENCY', 'ARS'),
            'items': [
                {
                    'item_id': str(item.product.code),
                    'item_name': str(item.product.name),
                    'item_category': str(item.product.category.category_name) if getattr(item.product, 'category', None) else '',
                    'price': float(item.purchase_price) if item.purchase_price else 0.0,
                    'quantity': int(item.quantity)
                } for item in ordered_products
            ]
        }
        
        context = {
            'order': order,
            'whatsapp_link': whatsapp_link,
            'order_number': order_number,
            'ordered_products': ordered_products,
            'is_new_purchase': is_new_purchase,
            'meta_payload': meta_payload,
            'ga4_payload': ga4_payload,
        }
        
        return render(request, 'orders/whatsapp_redirect.html', context)
        
    except Order.DoesNotExist:
        messages.warning(request, "Orden no encontrada")
        return redirect('account:my_orders')

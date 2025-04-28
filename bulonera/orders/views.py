from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages, auth
import json
import datetime
import urllib.parse
from django.http import JsonResponse
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.urls import reverse
from django.conf import settings

#Local
from .models import Payment, Order, OrderProduct
from .forms import OrderForm
#from account.models import *
from cart.models import CartItem
from store.models import Product

# Create your views here.

#Crear Payment
@login_required
def payments(request):
    if request.method == 'POST':
        try:
            # Intentar cargar el JSON de manera segura
            body = json.loads(request.body)
            
            # Validar campos críticos
            required_fields = ['orderID', 'transID', 'payment_method', 'status']
            for field in required_fields:
                if field not in body:
                    return JsonResponse({
                        'error': f'Falta el campo requerido: {field}'
                    }, status=400)

            # Buscar la orden de manera más segura
            try:
                order = Order.objects.get(
                    user=request.user, 
                    is_ordered=False, 
                    order_number=body['orderID']
                )
            except Order.DoesNotExist:
                return JsonResponse({
                    'error': 'Orden no encontrada'
                }, status=400)

            # Crear Payment
            payment = Payment(
                user=request.user,
                payment_id=body['transID'],
                payment_method=body['payment_method'],
                amount_id=str(order.order_total),  # Convertir a string
                status=body['status'],
            )
            payment.save()
            
            # Actualizar orden
            order.payment = payment
            order.is_ordered = True
            order.save()
            
            # Procesar items del carrito
            cart_items = CartItem.objects.filter(user=request.user)
            
            for item in cart_items:
                orderproduct = OrderProduct()
                orderproduct.order_id = order.id
                orderproduct.payment = payment
                orderproduct.user_id = request.user.id
                orderproduct.product_id = item.product_id
                orderproduct.quantity = item.quantity
                orderproduct.product_price = item.product.price
                orderproduct.ordered = True
                orderproduct.save()
                
                cart_item = CartItem.objects.get(id=item.id)
                product_variation = cart_item.variation.all()
                orderproduct = OrderProduct.objects.get(id=orderproduct.id)
                orderproduct.variation.set(product_variation)
                orderproduct.save()
                
                product = Product.objects.get(id=item.product_id)
                product.stock -= item.quantity
                product.save()
            
            # Limpiar carrito
            CartItem.objects.filter(user=request.user).delete()
            
            # Enviar correo electrónico (opcional)
            mail_subject = 'Tu compra fue realizada!'
            body = render_to_string('orders/order_recieved_email.html', {
                'user': request.user,
                'order': order,
            })
            
            to_email = request.user.email
            send_email = EmailMessage(mail_subject, body, to=[to_email])
            send_email.send()
            
            # Generar mensaje para WhatsApp
            message = f"""🛍️ Nueva Orden de Compra 🛒
                ID de Orden: {order.order_number}
                Cliente: {order.full_name()}
                Teléfono: {order.phone}
                Email: {order.email}
                Productos:
            """
            # Obtener productos de la orden
            ordered_products = OrderProduct.objects.filter(order=order)
            for product_item in ordered_products:
                message += f"- {product_item.product.name} (Cant: {product_item.quantity}) - ${product_item.product_price}\n"
            
            message += f"\nTotal: ${order.order_total}"
            
            # Codificar mensaje para URL
            encoded_message = urllib.parse.quote(message)
            
            # Número de WhatsApp de la empresa (REEMPLAZAR)
            phone_number = settings.WHATSAPP_NUMBER
            
            # Generar enlace de WhatsApp
            whatsapp_link = f"https://wa.me/{phone_number}?text={encoded_message}"
            
            # Devolver respuesta con enlace de WhatsApp
            # Respuesta exitosa
            data = {
                'status': 'success',
                'whatsapp_link': whatsapp_link,
                'order_number': order.order_number,
                'transID': payment.payment_id,
            }
            
            return JsonResponse(data)
        
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=400)
    
    elif request.method == 'GET' and request.GET.get('whatsapp') == 'true':
        order_number = request.GET.get('order_number')
        
        try:
            # Buscar la orden
            order = Order.objects.get(
                user=request.user, 
                is_ordered=False, 
                order_number=order_number
            )
            
            # Crear un Payment "virtual" para WhatsApp
            payment = Payment(
                user=request.user,
                payment_id=f"WA-{order_number}",  # Identificador único para pagos por WhatsApp
                payment_method="WhatsApp",
                amount_id=str(order.order_total),
                status="Pending",  # El pago está pendiente hasta que se confirme en WhatsApp
            )
            payment.save()
            
            # Actualizar orden
            order.payment = payment
            order.is_ordered = True  # Marcar como ordenado aunque el pago esté pendiente
            order.save()
            
            # Procesar items del carrito
            cart_items = CartItem.objects.filter(user=request.user)
            
            for item in cart_items:
                orderproduct = OrderProduct()
                orderproduct.order_id = order.id
                orderproduct.payment = payment
                orderproduct.user_id = request.user.id
                orderproduct.product_id = item.product_id
                orderproduct.quantity = item.quantity
                orderproduct.product_price = item.product.price
                orderproduct.ordered = True
                orderproduct.save()
                
                cart_item = CartItem.objects.get(id=item.id)
                product_variation = cart_item.variation.all()
                orderproduct = OrderProduct.objects.get(id=orderproduct.id)
                orderproduct.variation.set(product_variation)
                orderproduct.save()
                
                # Actualizamos el stock si queremos
                # O podemos comentar esto hasta confirmar el pago en WhatsApp
                product = Product.objects.get(id=item.product_id)
                product.stock -= item.quantity
                product.save()
            
            # Limpiar carrito
            CartItem.objects.filter(user=request.user).delete()
            
            # Enviar correo de confirmación si lo deseas
            # ...
            
            # Redirigir a WhatsApp
            return redirect('whatsapp_redirect') + f'?order_number={order_number}'
            
        except Order.DoesNotExist:
            return redirect('cart')
    
    # Si no es un método POST o GET con parámetro whatsapp
    return JsonResponse({
        'error': 'Método no permitido'
    }, status=405)

def place_orders(request, total=0, quantity=0):
    current_user = request.user
    cart_items = CartItem.objects.filter(user=current_user)
    cart_count = cart_items.count()
    
    if cart_count <= 0:
        return redirect('store')
    
    for cart_item in cart_items:
        total = sum(item.sub_total for item in cart_items)
        quantity += cart_item.quantity
        
    if request.method == 'POST':
        form = OrderForm(request.POST)
        
        if form.is_valid():
            try:
                data = Order()
                data.user = current_user
                data.first_name = form.cleaned_data['first_name']
                data.last_name = form.cleaned_data['last_name']
                data.phone = form.cleaned_data['phone']
                data.email = form.cleaned_data['email']
                data.address_line_1 = form.cleaned_data['address_line_1']
                data.address_line_2 = form.cleaned_data['address_line_2']
                data.country = form.cleaned_data['country']
                data.city = form.cleaned_data['city']
                data.state = form.cleaned_data['state']
                data.order_note = form.cleaned_data['order_note']
                data.order_total = total
                data.ip = request.META.get('REMOTE_ADDR')
                data.save()
                
                yr=int(datetime.date.today().strftime('%Y'))
                mt=int(datetime.date.today().strftime('%m'))
                dt=int(datetime.date.today().strftime('%d'))
                d = datetime.date(yr,mt,dt)
                current_date = d.strftime("%Y%m%d")
                order_number = current_date + str(data.id)
                data.order_number = order_number
                data.save()
                
                # Agregar productos al OrderProduct y limpiar el carrito
                for cart_item in cart_items:
                    orderproduct = OrderProduct()
                    orderproduct.order_id = data.id
                    orderproduct.user_id = current_user.id
                    orderproduct.product_id = cart_item.product_id
                    orderproduct.quantity = cart_item.quantity
                    orderproduct.purchase_price = cart_item.purchase_price
                    orderproduct.ordered = False
                    orderproduct.save()
                    
                    # Guardar las variaciones si existen
                    if cart_item.variation.exists():
                        product_variation = cart_item.variation.all()
                        orderproduct.variation.set(product_variation)
                        orderproduct.save()
                
                # Limpiar el carrito después de crear la orden
                CartItem.objects.filter(user=current_user).delete()
                
                # Redirigir a WhatsApp
                whatsapp_url = f"{reverse('whatsapp_redirect')}?order_number={order_number}"
                print(f"Redirigiendo a: {whatsapp_url}")  # Imprime para depuración
                return redirect(whatsapp_url)
                
            except Exception as e:
                import traceback
                print(f"Error al crear la orden: {str(e)}")
                print(traceback.format_exc())
                # Aquí puedes agregar un mensaje para el usuario
                messages.error(request, f"Error al procesar la orden: {str(e)}")
                
        else:
            print("Formulario inválido:")
            print(form.errors)  # Imprime los errores del formulario
            
        # Si llegamos aquí, hubo un error o el formulario no es válido
        cart_items = CartItem.objects.filter(user=current_user)
        context = {
            'form': form,  # Incluir el formulario con errores
            'cart_items': cart_items,
            'total': total,
            'quantity': quantity,
        }
        template_name = 'cart/checkout.html'
        return render(request, template_name, context)
    else:
        # Para solicitudes GET, simplemente mostrar el formulario
        cart_items = CartItem.objects.filter(user=current_user)
        form = OrderForm()
        context = {
            'form': form,
            'cart_items': cart_items,
            'total': total,
            'quantity': quantity,
        }
        template_name = 'cart/checkout.html'
        return render(request, template_name, context)

def order_complete(request, order_number):
    try:
        order = Order.objects.get(order_number=order_number)
        ordered_products = OrderProduct.objects.filter(order_id=order.id)

        subtotal = 0
        for i in ordered_products:
            subtotal += i.purchase_price * i.quantity
        
        # Obtener el payment relacionado con la orden
        try:
            payment = Payment.objects.get(order=order)
            transID = payment.payment_id
        except Payment.DoesNotExist:
            payment = None
            transID = ""
        
        context = {
            'order': order,
            'ordered_products': ordered_products,
            'order_number': order.order_number,
            'transID': transID,
            'payment': payment,
            'subtotal': subtotal,
            'status': order.status
        }
        template_name = 'orders/order_complete.html'
        return render(request, template_name, context)
    
    except Order.DoesNotExist:
        return redirect('my_orders')

@login_required
def whatsapp_redirect(request):
    order_number = request.GET.get('order_number')
    
    try:
        order = Order.objects.get(order_number=order_number, user=request.user)
        
        # Mensaje inicial
        message = f"""🛒 *Nueva Orden de Compra*

🆔 *ID de Orden:* {order.order_number}
👤 *Cliente:* {order.full_name()}
📞 *Teléfono:* {order.phone}
📧 *Email:* {order.email}
📍 *Dirección:* {order.address_line_1}, {order.city}, {order.state}

📦 *Productos Ordenados:*
"""
        # Obtener productos
        ordered_products = OrderProduct.objects.filter(order=order)
        for i, product_item in enumerate(ordered_products, 1):
            # Variaciones (si existen)
            variations = product_item.variation.all()
            var_str = ""
            if variations.exists():
                var_str = " - " + ", ".join([f"{v.variation_category}: {v.variation_value}" for v in variations])

            message += f"{i}. {product_item.product.name} 📦 (Cantidad: {product_item.quantity}) 💲 {product_item.purchase_price:.2f}{var_str}\n"
        
        # Total
        message += f"""\n💰 *Total de la Orden:* ${order.order_total:.2f}"""

        # Codificar mensaje para WhatsApp
        encoded_message = urllib.parse.quote(message)
        
        # Número de WhatsApp de la empresa
        phone_number = settings.WHATSAPP_NUMBER
        
        # Crear link
        whatsapp_link = f"https://wa.me/{phone_number}?text={encoded_message}"
        
        return render(request, 'orders/whatsapp_redirect.html', {
            'order': order,
            'whatsapp_link': whatsapp_link,
            'order_number': order_number
        })
    
    except Order.DoesNotExist:
        return redirect('cart')

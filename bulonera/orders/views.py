from django.shortcuts import render, redirect
import json
from django.http import JsonResponse
from django.core.mail import EmailMessage
from django.template.loader import render_to_string

#Local
from .models import Payment, Order, OrderProduct
from .forms import OrderForm
from cart.models import CartItem
from store.models import Product

# Create your views here.

def payments(request):
    body = json.loads(request.body)
    order = Order.objects.get(user=request.user, is_ordered=False, order_number=body['orderID'])
    
    payment = Payment(
        user = request.user,
        payment_id = body['transID'],
        payment_method = body['payment_method'],
        amountID = order.order_total.amount,
        status = body['status'],
    )
    payment.save()
    order.payment = payment
    order.is_ordered = True
    order.save()
    
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
        
    cart_items = CartItem.objects.filter(user=request.user).delete()
    
    mail_subject = 'Tu compra fue realizada!'
    body = render_to_string('orders/order_received_email.html', {
        'user': request.user,
        'order' : order,
    })
    
    to_email = request.user.email
    send_email = EmailMessage(mail_subject, body, to=[to_email])
    send_email.send()
    
    data = {
        'order_number' : order.order_number,
        'transID' : payment.payment_id,
    }
        
    return JsonResponse(data)

def place_orders(request):
    template_name = 'orders.html'
    return render(request, template_name)

def order_complete(request):
    template_name = 'order_complete.html'
    return render(request, template_name)

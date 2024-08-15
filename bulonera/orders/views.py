from django.shortcuts import render, redirect
import json
import datetime
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

def place_orders(request, total=0, quantity=0):
    current_user = request.user
    cart_items = CartItem.objects.filter(user=current_user)
    cart_count = cart_items.count()
    
    if cart_count <= 0:
        return redirect('store')
    
    for cart_item in cart_items:
        total += (cart_item.product.price * cart_item.quantity)
        quantity += cart_item.quantity
        
    if request.method == 'POST':
        form = OrderForm(request.POST)
        
        if form.is_valid():
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
            
            order = Order.objects.get(user=current_user, is_ordered=False, order_number=order_number)
            context = {
                'order' : order,
                'cart_items' : cart_items,
                'total' : total
            }
            template_name = 'orders/payment.html'
            return render(request, template_name, context)
            
    else:        
        template_name = 'checkout'
        return render(request, template_name)

def order_complete(request):
    order_number = request.GET.get('order_number')
    transID = request.GET.get('payment_id')
    try:
        order = Order.objects.get(order_number=order_number, is_ordered=True)
        ordered_products = OrderProduct.objects.filter(order_id=order.id)
        
        subtotal = 0
        for i in ordered_products:
            subtotal += i.product_price * i.quantity
        
        payment = Payment.objects.get(payment_id=transID)
        
        context = {
            'order' : order,
            'ordered_products' : ordered_products,
            'order_number' : order.order_number,
            'transID' : payment.payment_id,
            'payment' : payment,
            'subtotal' : subtotal,
        }
        template_name = 'orders/order_complete.html'
        return render(request, template_name, context)
    
    except (Payment.DoesNotExist, Order.DoesNotExist):
        return redirect('home')

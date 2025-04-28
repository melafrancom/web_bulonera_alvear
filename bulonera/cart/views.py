from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse

from .models import Cart, CartItem
from store.models import Product, Variation

# Create your views here.

##### Primero: Nuestro carrito es único. Si no tenemos, lo creamos #####
def _cart_id(request):
    cart = request.session.session_key
    if not cart:
        cart = request.session.create()
    return cart


#### Segundo: podemos ir agregando o eliminando productos/items del carrito #####
def add_cart(request, product_id):
    product = Product.objects.get(id=product_id)
    current_user = request.user
    
    # Get product price (regular or discounted)
    if product.is_on_sale and product.sale_price:
        price_to_use = product.sale_price
    else:
        price_to_use = product.price
    
        # Obtener la cantidad desde GET o POST
    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
    else:
        # Obtener desde parámetros GET
        quantity = int(request.GET.get('qty', 1))
        
    # Usuario identificado
    if current_user.is_authenticated:
        product_variation = []
        
        if request.method == 'POST':
            for item in request.POST:
                key = item
                value = request.POST[key]
                
                try:
                    variation = Variation.objects.get(product=product, variation_category__iexact=key, variation_value__iexact=value)
                    product_variation.append(variation)
                except:
                    pass
            # Get quantity from form
            quantity = int(request.POST.get('quantity', 1))# obtener la cantidad del POST si envías cantidad ahí.  
            
        is_cart_item_exists = CartItem.objects.filter(product=product, user=current_user).exists()
        if is_cart_item_exists:
            cart_item = CartItem.objects.filter(product=product, user=current_user)
            
            ex_var_list = []
            id = []
            for item in cart_item:
                existing_variation = item.variation.all()
                ex_var_list.append(list(existing_variation))
                id.append(item.id)
                
            if product_variation in ex_var_list:
                index = ex_var_list.index(product_variation)
                item_id = id[index]
                item = CartItem.objects.get(product=product, id=item_id)
                item.quantity += quantity
                item.save()
            else:
                item = CartItem.objects.create(
                    product=product, 
                    quantity=quantity,
                    user=current_user,
                    purchase_price=price_to_use  # Añadido el precio
                )
                if len(product_variation) > 0:
                    item.variation.clear()
                    item.variation.add(*product_variation)
                item.save()
        else:
            cart_item = CartItem.objects.create(
                product=product,
                quantity=quantity,
                user=current_user,
                purchase_price=price_to_use  # Añadido el precio
            )
            if len(product_variation) > 0:
                cart_item.variation.clear()
                cart_item.variation.add(*product_variation)
            cart_item.save()
    
    # Usuarios no identificados:
    else:
        product_variation = []
        
        if request.method == 'POST':
            for item in request.POST:
                key = item
                value = request.POST[key]
                
                try:
                    variation = Variation.objects.get(product=product, variation_category__iexact=key, variation_value__iexact=value)
                    product_variation.append(variation)
                except:
                    pass
        if request.method == 'POST':
            quantity = int(request.POST.get('quantity', 1))
        else:
            quantity = 1

        try:
            cart = Cart.objects.get(cart_id=_cart_id(request))
        except Cart.DoesNotExist:
            cart = Cart.objects.create(
                cart_id=_cart_id(request)
            )
        cart.save()
        
        is_cart_item_exists = CartItem.objects.filter(product=product, cart=cart).exists()
        if is_cart_item_exists:
            cart_item = CartItem.objects.filter(product=product, cart=cart)
            
            ex_var_list = []
            id = []
            for item in cart_item:
                existing_variation = item.variation.all()
                ex_var_list.append(list(existing_variation))
                id.append(item.id)
                
            if product_variation in ex_var_list:
                index = ex_var_list.index(product_variation)
                item_id = id[index]
                item = CartItem.objects.get(product=product, id=item_id)
                item.quantity += quantity
                item.save()
            else:
                item = CartItem.objects.create(
                    product=product,
                    quantity=quantity,
                    cart=cart,
                    purchase_price=price_to_use  # Añadido el precio
                )
                if len(product_variation) > 0:
                    item.variation.clear()
                    item.variation.add(*product_variation)
                item.save()     
        else:
            cart_item = CartItem.objects.create(
                product=product,
                quantity=quantity,
                cart=cart,
                purchase_price=price_to_use  # Añadido el precio
            )
            if len(product_variation) > 0:
                cart_item.variation.clear()
                cart_item.variation.add(*product_variation)
            cart_item.save()
            
    # Redirigir siempre a la página anterior al final de la función
    # Verificar si es una solicitud AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    else:
        # Redirigir a la página anterior o a la tienda
        referer_url = request.META.get('HTTP_REFERER')
        if referer_url:
            return HttpResponseRedirect(referer_url)
        else:
            return redirect('store')

def remove_cart(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)
    try:
        if request.user.is_authenticated:
            cart_item = CartItem.objects.get(product=product, user=request.user, id=cart_item_id)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_item = CartItem.objects.get(product=product, cart=cart, id=cart_item_id)
        
        if cart_item.quantity > 1:
            cart_item.quantity -= 1
            cart_item.save()
        else:
            cart_item.delete()
        
    except:
        pass
    
    return redirect('cart')

def remove_cart_item(request, product_id, cart_item_id):
    product = get_object_or_404(Product, id=product_id)
    
    if request.user.is_authenticated:
        cart_item = CartItem.objects.get(product=product, user=request.user, id=cart_item_id)
    else:
        cart = Cart.objects.get(cart_id=_cart_id(request))
        cart_item = CartItem.objects.get(product=product, cart=cart, id=cart_item_id)
        
    cart_item.delete()
    return redirect('cart')

def get_cart_data(request):
    total = 0
    quantity = 0
    cart_items_data = []#para almacenar los detalles de los artículos en el carrito.
    
    try:
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)
        
        for item in cart_items:
            total += item.sub_total
            quantity += item.quantity
            
            # Construir datos de items para JSON
            cart_items_data.append({
                'id': item.id,
                'name': item.product.name,
                'price': float(item.sub_total),
                'quantity': item.quantity,
                'image': item.product.images.url if item.product.images else '',
            })
    
    except ObjectDoesNotExist:
        pass
    
    return JsonResponse({
        'cart_count': quantity,
        'cart_total': float(total),
        'cart_items': cart_items_data
    })

#### Tercero: como resultado tenemos nuestro carrito. ####

def cart(request, total=0, quantity=0, cart_items=None):
    try:
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id = _cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)
            
        for cart_item in cart_items:
            total = sum(item.sub_total for item in cart_items)
            quantity += cart_item.quantity
            
        
    except ObjectDoesNotExist:
        pass
    
    context = {
        'total' : total,
        'quantity' : quantity,
        'cart_items' : cart_items,
        
    }
    template_name = 'cart/cart.html'
    return render(request, template_name, context)



##### Cuarto: realizamos los totales del carrito #####

@login_required(login_url='login')
def checkout(request, total=0, quantity=0, cart_items=None):
    try:
        if request.user.is_authenticated:
            cart_items = CartItem.objects.filter(user=request.user, is_active=True)
        else:
            cart = Cart.objects.get(cart_id=_cart_id(request))
            cart_items = CartItem.objects.filter(cart=cart, is_active=True)
        
        for cart_item in cart_items:
            total = sum(item.sub_total for item in cart_items)
            quantity += cart_item.quantity
            
    except ObjectDoesNotExist:
        pass
    
    context = {
        'total' : total,
        'quantity' : quantity,
        'cart_items' : cart_items,
        
    }
    template_name = 'cart/checkout.html'
    return render(request, template_name, context)


"""
El código no maneja potenciales errores como variaciones inexistentes o productos no encontrados. Se recomienda agregar manejo de excepciones para casos como estos.
"""

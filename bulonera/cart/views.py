from django.shortcuts import render, redirect, get_object_or_404
from .models import Cart, CartItem, CartAdmin, CartItemAdmin
from django.contrib.auth.decorators import login_required


# Create your views here.
##### Primero para estar dentro del carrito es necesario estar logueados #####

@login_required(login_url='login')
def checkout(request):
    pass
    #return render(request, 'cart/checkout.html')




##### Segundo: una vez logueados, nuestro carrito es único. Si no tenemos, lo creamos #####
def _cart_id(request):
    cart = request.session.session_key
    if not cart:
        cart = request.session.create()
    return cart





#### Tercero: podemos ir agregando o eliminando productos/items del carrito #####
def cart_add(request):
    pass
    #return redirect('cart')

def cart_remove(request):
    pass
    #return redirect('cart')

def remove_cart_item(request):
    pass
    #return redirect('cart')







#### Cuarto: como resultado tenemos nuestro carrito. ####

def cart(request):
    pass
    #return render(request, 'cart/cart.html')


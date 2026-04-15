"""Cart Web URLs"""
from django.urls import path
from cart.web.views.views import (
    cart_view,
    add_cart,
    remove_cart,
    remove_cart_item,
    get_cart_data,
    checkout
)

app_name = 'cart'

urlpatterns = [
    path('', cart_view, name='cart'),
    path('add_cart/<int:product_id>/', add_cart, name='add_cart'),
    path('remove_cart/<int:product_id>/<int:cart_item_id>/', remove_cart, name='remove_cart'),
    path('remove_cart_item/<int:product_id>/<int:cart_item_id>/', remove_cart_item, name='remove_cart_item'),
    path('checkout/', checkout, name='checkout'),
    path('get-cart-data/', get_cart_data, name='get_cart_data'),
]

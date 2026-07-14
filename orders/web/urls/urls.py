"""Orders Web URLs"""
from django.urls import path
from orders.web.views.views import (
    place_order,
    payments,
    order_complete,
    order_detail,
    whatsapp_redirect,
    orders_index
)

app_name = 'orders'

urlpatterns = [
    path('', orders_index, name='orders_index'),
    path('place_order/', place_order, name='place_orders'),
    path('payments/', payments, name='payments'),
    path('order_complete/<str:order_number>/', order_complete, name='order_complete'),
    path('order_detail/<str:order_number>/', order_detail, name='order_detail'),
    path('whatsapp_redirect/', whatsapp_redirect, name='whatsapp_redirect'),
]


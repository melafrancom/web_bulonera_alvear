"""Cart API URLs"""
from rest_framework.routers import DefaultRouter
from django.urls import path
from cart.api.views.views import CartViewSet

app_name = 'cart_api'

router = DefaultRouter()

# Rutas manuales para mejor control
urlpatterns = [
    path('', CartViewSet.as_view({'get': 'list'}), name='cart-list'),
    path('add/', CartViewSet.as_view({'post': 'add'}), name='cart-add'),
    path('<int:pk>/update/', CartViewSet.as_view({'patch': 'update'}), name='cart-update'),
    path('<int:pk>/remove/', CartViewSet.as_view({'delete': 'remove'}), name='cart-remove'),
    path('clear/', CartViewSet.as_view({'delete': 'clear'}), name='cart-clear'),
    path('count/', CartViewSet.as_view({'get': 'count'}), name='cart-count'),
]

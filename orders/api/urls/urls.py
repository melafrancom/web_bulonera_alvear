"""Orders API URLs"""
from rest_framework.routers import DefaultRouter
from django.urls import path
from orders.api.views.views import OrderViewSet

app_name = 'orders_api'

router = DefaultRouter()

# Rutas manuales para mejor control
urlpatterns = [
    path('', OrderViewSet.as_view({'get': 'list', 'post': 'create_order'}), name='order-list'),
    path('<str:order_number>/', OrderViewSet.as_view({'get': 'retrieve'}), name='order-detail'),
    path('<str:order_number>/process_payment/', OrderViewSet.as_view({'post': 'process_payment'}), name='order-process-payment'),
    path('<str:order_number>/whatsapp_link/', OrderViewSet.as_view({'get': 'whatsapp_link'}), name='order-whatsapp-link'),
    path('<str:order_number>/process_whatsapp/', OrderViewSet.as_view({'post': 'process_whatsapp'}), name='order-process-whatsapp'),
]

"""Store URLs - Redirects to web URLs"""
from django.urls import path, include
from store.web.urls import app_name

urlpatterns = [
    path('', include('store.web.urls')),
]

__all__ = ['urlpatterns', 'app_name']

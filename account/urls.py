"""Account URLs - Redirects to web URLs"""
from django.urls import path, include
from account.web.urls import app_name

urlpatterns = [
    path('', include('account.web.urls')),
]

__all__ = ['urlpatterns', 'app_name']

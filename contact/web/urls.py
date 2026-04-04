"""Contact Web URLs"""
from django.urls import path
from contact.web.views import contact_view, contact_success

urlpatterns = [
    path('', contact_view, name='contact'),
    path('success/', contact_success, name='contact_success'),
]

app_name = 'contact_web'

__all__ = ['urlpatterns', 'app_name']

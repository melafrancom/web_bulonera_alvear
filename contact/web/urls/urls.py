"""Contact Web URLs"""
from django.urls import path
from contact.web.views.views import contact_view, contact_success, whatsapp_lead_redirect

app_name = 'contact'

urlpatterns = [
    path('', contact_view, name='contact'),
    path('success/', contact_success, name='contact_success'),
    path('whatsapp-lead/', whatsapp_lead_redirect, name='whatsapp_lead_redirect'),
]

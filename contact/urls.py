# urls.py - Contact Web URLs (importa desde web/)
from django.urls import path, include

# Importar URLs de la layer web
from contact.web.urls import urlpatterns as web_urlpatterns

urlpatterns = web_urlpatterns

# NOTA: Para usar la API REST, agregar a web_bulonera/urls.py:
# path('api/', include('contact.api.urls')),


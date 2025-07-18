"""
URL configuration for bulonera project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings
from django.contrib.sitemaps.views import sitemap
from django.contrib.sitemaps import GenericSitemap
#local apps
from . import views
from store.models import Product

info_dict = {
    'queryset': Product.objects.all(),
    'date_field': 'modified_date',
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('store/', include('store.urls')),
    path('cart/', include('cart.urls')),
    path('account/', include('account.urls')),
    path('orders/', include('orders.urls')),
    path('contact/', include('contact.urls')),
    #Others:
    path('return-policy/', views.returnPolicy, name='return_policy'),
    path('terms-and-conditions/', views.termsAndConditions, name='terms_and_conditions'),
    path('privacy-and-warranty/', views.privacyAndwarranty, name='privacy_and_warranty'),
    path('location/', views.location, name='location'),
    path('history/', views.history, name='history'),
    # URLs para sitemaps y robots.txt
    path('sitemap.xml', sitemap, {'sitemaps': {'products': GenericSitemap(info_dict, priority=0.8)}}, name='django.contrib.sitemaps.views.sitemap'),
    path("robots.txt", views.robots_txt),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


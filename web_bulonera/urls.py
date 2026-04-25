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
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django.views.static import serve
#local apps
from . import views
from store.sitemaps import ProductSitemap, CategorySitemap, SubCategorySitemap
from blog.sitemaps import sitemaps as blog_sitemaps
from store.web.views import views as store_views  # Fase 1 - SEO Refactoring

# Sitemaps configuration
sitemaps = {
    'products': ProductSitemap,
    'categories': CategorySitemap,
    'subcategories': SubCategorySitemap,
    **blog_sitemaps,  # Incluir blog-posts y blog-tags
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    
    # URLs planas para productos (Fase 1 - SEO Refactoring)
    # Exponer /p/<slug>/ en la raíz para máxima URL flatness
    path('p/<slug:product_slug>/', store_views.product_detail, name='product_detail_flat'),
    
    # Web URLs (Templates HTML)
    path('store/', include(('store.web.urls', 'store'))),
    path('blog/', include(('blog.web.urls', 'blog'))),
    path('cart/', include(('cart.web.urls', 'cart'))),
    path('account/', include(('account.web.urls', 'account'))),
    path('orders/', include(('orders.web.urls', 'orders'))),
    path('contact/', include(('contact.web.urls', 'contact'))),
    
    # API REST v1
    path('api/v1/store/', include('store.api.urls.urls')),
    path('api/v1/category/', include('category.api.urls.urls')),
    path('api/v1/blog/', include('blog.api.urls.urls')),
    path('api/v1/cart/', include('cart.api.urls.urls')),
    path('api/v1/orders/', include('orders.api.urls.urls')),
    path('api/v1/account/', include('account.api.urls.urls')),
    path('api/v1/contact/', include('contact.api.urls.urls')),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    #Others:
    path('return-policy/', views.returnPolicy, name='return_policy'),
    path('terms-and-conditions/', views.termsAndConditions, name='terms_and_conditions'),
    path('privacy-and-warranty/', views.privacyAndwarranty, name='privacy_and_warranty'),
    path('location/', views.location, name='location'),
    path('history/', views.history, name='history'),
    path('offline/', views.offline, name='offline'),
    
    # PWA - Service Worker (debe servirse desde la raíz, no /static/)
    path('sw.js', serve, {'document_root': settings.STATIC_ROOT, 'path': 'js/sw.js'}, name='sw'),
    
    # PWA - Manifest (debe servirse desde la raíz con MIME correcto)
    path('manifest.json', serve, {'document_root': settings.STATIC_ROOT, 'path': 'images/manifest.json'}, name='manifest'),
    
    # URLs para sitemaps y robots.txt
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    path("robots.txt", views.robots_txt),
    path("llms.txt", views.llms_txt),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


# Error handlers
handler404 = 'web_bulonera.error_handlers.handler404'
handler500 = 'web_bulonera.error_handlers.handler500'
handler403 = 'web_bulonera.error_handlers.handler403'
handler400 = 'web_bulonera.error_handlers.handler400'

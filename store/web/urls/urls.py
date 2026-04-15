"""Store Web URLs"""
from django.urls import path
from store.web.views import views

urlpatterns = [
    path('', views.store, name="store"),
    path('offers/', views.offers, name='offers'),
    path('category/<slug:category_slug>/', views.store, name="products_by_category"),
    path('category/<slug:category_slug>/subcategory/<slug:subcategory_slug>/', views.products_by_subcategory, name='products_by_subcategory'),
    path('category/<slug:category_slug>/product/<slug:product_slug>/', views.product_detail, name="product_detail"),
    path('search/', views.search, name='search'),
    path('submit_review/<int:product_id>/', views.submit_review, name='submit_review'),
    path('feeds/facebook.csv', views.facebook_feed, name='facebook_feed'),
    path('feeds/google-merchant/', views.google_merchant_feed, name='google_merchant_feed'),
    path('faq/', views.faq, name='faq'),
]

app_name = 'store'

__all__ = ['urlpatterns', 'app_name']

"""Store Web Module"""
from store.web.forms import ReviewForm, ProductImportForm
from store.web.views.views import (
    store,
    products_by_subcategory,
    product_detail,
    search,
    submit_review,
    offers,
    faq,
    facebook_feed,
    google_merchant_feed,
)

__all__ = [
    'ReviewForm',
    'ProductImportForm',
    'store',
    'products_by_subcategory',
    'product_detail',
    'search',
    'submit_review',
    'offers',
    'faq',
    'facebook_feed',
    'google_merchant_feed',
]

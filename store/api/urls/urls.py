"""Store API URLs"""
from rest_framework.routers import DefaultRouter
from store.api.views.views import (
    ProductViewSet, SearchViewSet, ReviewViewSet,
    FAQViewSet, CarouselViewSet, FeedViewSet
)

router = DefaultRouter()
router.register(r'products', ProductViewSet, basename='products')
router.register(r'search', SearchViewSet, basename='search')
router.register(r'reviews', ReviewViewSet, basename='reviews')
router.register(r'faqs', FAQViewSet, basename='faqs')
router.register(r'carousel', CarouselViewSet, basename='carousel')
router.register(r'feeds', FeedViewSet, basename='feeds')

urlpatterns = router.urls
app_name = 'store_api'

__all__ = ['urlpatterns', 'app_name']

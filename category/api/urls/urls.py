"""Category API URLs"""
from rest_framework.routers import DefaultRouter
from category.api.views.views import CategoryViewSet, SubCategoryViewSet

app_name = 'category_api'

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'subcategories', SubCategoryViewSet, basename='subcategory')

urlpatterns = router.urls

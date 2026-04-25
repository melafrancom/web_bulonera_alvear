"""Blog API URLs - DRF router configuration"""
from rest_framework.routers import DefaultRouter
from blog.api.views import PostViewSet, PostTagViewSet

app_name = 'blog_api'

router = DefaultRouter()
router.register(r'posts', PostViewSet, basename='posts')
router.register(r'tags', PostTagViewSet, basename='tags')

urlpatterns = router.urls

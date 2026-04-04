"""Contact API URLs Package"""
from rest_framework.routers import DefaultRouter
from contact.api.views import ContactOptionViewSet

router = DefaultRouter()
router.register(r'contact', ContactOptionViewSet, basename='contact')

urlpatterns = router.urls
app_name = 'contact_api'

__all__ = ['urlpatterns', 'app_name', 'router']

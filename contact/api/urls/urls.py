"""Contact API URLs"""
from rest_framework.routers import DefaultRouter
from contact.api.views.views import ContactOptionViewSet

app_name = 'contact_api'

router = DefaultRouter()
router.register(r'contact', ContactOptionViewSet, basename='contact')

urlpatterns = router.urls

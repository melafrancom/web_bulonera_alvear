"""Account API URLs"""
from rest_framework.routers import DefaultRouter
from account.api.views.views import RegistrationAPIView, UserProfileAPIView

router = DefaultRouter()
router.register(r'auth', RegistrationAPIView, basename='auth')
router.register(r'account', UserProfileAPIView, basename='account')

urlpatterns = router.urls
app_name = 'account_api'

__all__ = ['urlpatterns', 'app_name']

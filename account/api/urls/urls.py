"""Account API URLs"""
from rest_framework.routers import DefaultRouter
from account.api.views.views import AuthViewSet, ProfileViewSet, PasswordResetViewSet

router = DefaultRouter()
router.register(r'auth', AuthViewSet, basename='auth')
router.register(r'profile', ProfileViewSet, basename='profile')
router.register(r'password', PasswordResetViewSet, basename='password')

urlpatterns = router.urls
app_name = 'account_api'

__all__ = ['urlpatterns', 'app_name']

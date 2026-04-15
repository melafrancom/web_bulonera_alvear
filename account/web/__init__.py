"""Account Web Module"""
from account.web.forms import RegistrationForm, UserForm, UserProfileForm
from account.web.views.views import (
    register,
    login,
    logout,
    activate,
    dashboard,
    forgotPassword,
    resetpassword_validate,
    resetPassword,
    my_orders,
    edit_profile,
    change_password,
)

__all__ = [
    'RegistrationForm',
    'UserForm',
    'UserProfileForm',
    'register',
    'login',
    'logout',
    'activate',
    'dashboard',
    'forgotPassword',
    'resetpassword_validate',
    'resetPassword',
    'my_orders',
    'edit_profile',
    'change_password',
]

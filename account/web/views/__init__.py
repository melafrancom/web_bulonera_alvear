"""Account Web Views Module"""
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

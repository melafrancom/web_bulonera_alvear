"""Account Web Views"""
import urllib.parse
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required

from account.web.forms import RegistrationForm, UserForm, UserProfileForm
from account.models import Account, UserProfile
from account.services import (
    AccountRegistrationService,
    AccountLoginService,
    PasswordResetService,
    ProfileUpdateService,
    AccountActivationService,
    PasswordChangeService,
    DashboardService
)
from cart.services import CartService
from orders.models import Order

logger = logging.getLogger(__name__)


def register(request):
    """Vista de registro de nuevos usuarios"""
    form = RegistrationForm()
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            try:
                user = AccountRegistrationService.register(
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    email=form.cleaned_data['email'],
                    phone=form.cleaned_data.get('phone', ''),
                    password=form.cleaned_data['password'],
                    request=request
                )
                messages.success(request, 'Te has registrado exitosamente. Verifica tu email para activar tu cuenta.')
                return redirect(f'/account/login/?command=verification&email={user.email}')
            except Exception as e:
                logger.error(f"Error en registro: {e}")
                messages.error(request, 'Ocurrió un error durante el registro. Intenta nuevamente.')
    
    context = {'form': form}
    return render(request, 'account/register.html', context)


def login(request):
    """Vista de login"""
    if request.method == 'POST':
        email = request.POST.get('email', '')
        password = request.POST.get('password', '')
        
        user = AccountLoginService.authenticate_user(email, password)
        
        if user is not None:
            auth.login(request, user)
            messages.success(request, 'Has iniciado sesión exitosamente.')
            
            # Merge cart on login
            try:
                CartService.merge_cart_on_login(request, user)
            except Exception as e:
                logger.error(f"Error merging cart on login for user {user.email}: {e}")
            
            # Redirect to next page if specified
            url = request.META.get('HTTP_REFERER')
            try:
                query = urllib.parse.urlparse(url).query
                params = dict(x.split('=') for x in query.split('&') if '=' in x)
                if 'next' in params:
                    return redirect(params['next'])
            except Exception as e:
                logger.exception(f"Error parsing referer URL: {e}")
            
            return redirect('account:dashboard')
        else:
            messages.error(request, 'Los datos son incorrectos.')
            return redirect('account:login')
    
    return render(request, 'account/login.html')


@login_required(login_url='account:login')
def logout(request):
    """Vista de logout"""
    auth.logout(request)
    messages.success(request, 'Has cerrado sesión, muchas gracias.')
    return redirect('home')


def activate(request, uidb64, token):
    """Vista de activación de cuenta"""
    user = AccountActivationService.activate_account(uidb64, token)
    
    if user is not None:
        messages.success(request, 'Felicidades, tu cuenta está activa.')
        return redirect('account:login')
    else:
        messages.error(request, 'No se pudo completar la activación de la cuenta.')
        return redirect('account:register')


@login_required(login_url='account:login')
def dashboard(request):
    """Vista del dashboard del usuario"""
    dashboard_data = DashboardService.get_user_dashboard_data(request.user)
    userprofile = DashboardService.get_user_profile(request.user)
    
    # Breadcrumb
    breadcrumb_items = [
        {'name': 'Inicio', 'url': '/'},
        {'name': 'Dashboard', 'url': None}
    ]
    
    context = {
        'orders_count': dashboard_data['orders_count'],
        'new_orders_count': dashboard_data['new_orders_count'],
        'accepted_orders_count': dashboard_data['accepted_orders_count'],
        'completed_orders_count': dashboard_data['completed_orders_count'],
        'cancelled_orders_count': dashboard_data['cancelled_orders_count'],
        'userprofile': userprofile,
        'breadcrumb_items': breadcrumb_items,
    }
    
    return render(request, 'account/dashboard.html', context)


def forgotPassword(request):
    """Vista para solicitar recuperación de contraseña"""
    if request.method == 'POST':
        email = request.POST.get('email', '')
        success = PasswordResetService.send_reset_email(email, request)
        
        if success:
            messages.success(request, 'Un email fue enviado a tu bandeja de entrada para recuperar tu contraseña')
        else:
            # Por seguridad, mostramos el mismo mensaje aunque el email no exista
            messages.success(request, 'Si el email existe, recibirás instrucciones para recuperar tu contraseña')
        
        return redirect('account:login')
    
    return render(request, 'account/forgotPassword.html')


def resetpassword_validate(request, uidb64, token):
    """Vista para validar token de reset de contraseña"""
    user = PasswordResetService.validate_reset_token(uidb64, token)
    
    if user is not None:
        request.session['uid'] = str(user.pk)
        messages.success(request, 'Por favor escribe tu nueva contraseña')
        return redirect('account:resetPassword')
    else:
        messages.error(request, 'El link ha caducado')
        return redirect('account:login')


def resetPassword(request):
    """Vista para establecer nueva contraseña"""
    if request.method == 'POST':
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        if password == confirm_password:
            uid = request.session.get('uid')
            if uid:
                success = PasswordResetService.reset_password(uid, password)
                if success:
                    messages.success(request, 'La contraseña se actualizó correctamente')
                    return redirect('account:login')
                else:
                    messages.error(request, 'Ocurrió un error al actualizar la contraseña')
            else:
                messages.error(request, 'Sesión inválida')
                return redirect('account:forgotPassword')
        else:
            messages.error(request, 'La contraseña de confirmación no concuerda')
            return redirect('account:resetPassword')
    
    return render(request, 'account/resetPassword.html')


@login_required(login_url='account:login')
def my_orders(request):
    """Vista de pedidos del usuario"""
    orders = Order.objects.filter(user=request.user).order_by('-created_at')
    
    # Breadcrumb
    breadcrumb_items = [
        {'name': 'Inicio', 'url': '/'},
        {'name': 'Dashboard', 'url': reverse('account:dashboard')},
        {'name': 'Mis Órdenes', 'url': None}
    ]
    
    context = {
        'orders': orders,
        'breadcrumb_items': breadcrumb_items,
    }
    return render(request, 'account/my_orders.html', context)


@login_required(login_url='account:login')
def edit_profile(request):
    """Vista para editar perfil"""
    userprofile = get_object_or_404(UserProfile, user=request.user)
    
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILES, instance=userprofile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Tu información fue guardada con éxito.')
            return redirect('account:dashboard')
    else:
        user_form = UserForm(instance=request.user)
        profile_form = UserProfileForm(instance=userprofile)
    
    # Breadcrumb
    breadcrumb_items = [
        {'name': 'Inicio', 'url': '/'},
        {'name': 'Dashboard', 'url': reverse('account:dashboard')},
        {'name': 'Editar Perfil', 'url': None}
    ]
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'userprofile': userprofile,
        'breadcrumb_items': breadcrumb_items,
    }
    return render(request, 'account/edit_profile.html', context)


@login_required(login_url='account:login')
def change_password(request):
    """Vista para cambiar contraseña"""
    if request.method == 'POST':
        current_password = request.POST.get('current_password', '')
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')
        
        if new_password == confirm_password:
            success = PasswordChangeService.change_password(
                user=request.user,
                current_password=current_password,
                new_password=new_password
            )
            
            if success:
                messages.success(request, 'La contraseña se actualizó correctamente')
                return redirect('account:dashboard')
            else:
                messages.error(request, 'La contraseña actual no es válida.')
                return redirect('account:change_password')
        else:
            messages.error(request, 'La contraseña no coincide con la confirmación.')
            return redirect('account:change_password')
    
    # Breadcrumb
    breadcrumb_items = [
        {'name': 'Inicio', 'url': '/'},
        {'name': 'Dashboard', 'url': reverse('account:dashboard')},
        {'name': 'Cambiar Contraseña', 'url': None}
    ]
    
    context = {
        'breadcrumb_items': breadcrumb_items,
    }
    
    return render(request, 'account/change_password.html', context)


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

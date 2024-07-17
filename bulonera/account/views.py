from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes

from .forms import RegistrationForm, UserForm, UserProfileForm
from .models import Account, UserProfile
from cart.models import Cart, CartItem


# Create your views here.
def register(request):
    form = RegistrationForm()
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data['first_name']
            last_name = form.cleaned_data['last_name']
            phone = form.cleaned_data['phone']
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            username = email.split('@')[0]
            user = Account.objects.create_user(first_name=first_name, last_name=last_name, email=email, username=username, password=password)
            user.phone = phone
            user.save()

        profile = UserProfile()
        profile.user_id = user.id
        profile.profile_picture = 'default/default-user.png' #Ver a donde va está imagen.
        profile.save()
        
        current_site = get_current_site(request)
        mail_subject = 'Activa tu cuenta en Bulonera Alvear para continuar'
        body = render_to_string('account/account_verification_email.html', {
            'user' : user,
            'domain' : current_site,
            'uid' : urlsafe_base64_encode(force_bytes(user.pk)),
            'token' : default_token_generator.make_token(user),
        })
        to_email = email
        send_mail = email.send_mail(mail_subject, body, to = [to_email])
        send_mail.send()
        
        # messages.success(request, 'Te has registrado exitosamente')
        return redirect('/accounts/login/?command=verification&email='+email)
        
    context = {
        'form' : form
    }
    template_name = 'account/prueba.html'
    return render(request, template_name, context)


def login(request):
    template_name = 'account/prueba.html'
    return render(request, template_name)


@login_required(login_url='login')
def logout(request):
    auth.logout(request)
    messages.success(request, 'Has cerrado sesion, muchas gracias.')
    return redirect('login')

def activate(request):
    template_name = 'account/prueba.html'
    return render(request, template_name)


@login_required(login_url='login')
def dashboard(request):
    template_name = 'account/prueba.html'
    return render(request, template_name)

def forgotPassword(request):
    template_name = 'account/prueba.html'
    return render(request, template_name)

def resetPassword_validate():
    pass

def reserPassword():
    pass

def my_orders(request):
    template_name = 'account/prueba.html'
    return render(request, template_name)

@login_required(login_url='login')
def edit_profile(request):
    template_name = 'account/prueba.html'
    return render(request, template_name)

@login_required(login_url='login')
def change_password(request):
    template_name = 'account/prueba.html'
    return render(request, template_name)
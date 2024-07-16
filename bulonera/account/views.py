from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required

from .forms import RegistrationForm, UserForm, UserProfileForm
from .models import Account, UserProfile


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
    
    template_name = 'templates/prueba.html'
    return render(request, template_name)


def login(request):
    template_name = 'templates/login.html'
    return render(request, template_name)

@login_required(login_url='login')
def logout(request):
    auth.logout(request)
    messages.success(request, 'Has cerrado sesion, muchas gracias.')
    return redirect('login')

def activate(request):
    template_name = 'templates/activate.html'
    return render(request, template_name)


@login_required(login_url='login')
def dashboard(request):
    template_name = 'templates/dashboard.html'
    return render(request, template_name)

def forgotPassword(request):
    template_name = 'templates/forgotPassword.html'
    return render(request, template_name)

def resetPassword_validate():
    pass

def reserPassword():
    pass

def my_orders(request):
    template_name = 'templates/account/my_orders.html'
    return render(request, template_name)

@login_required(login_url='login')
def edit_profile(request):
    template_name = 'templates/account/edit_profile.html'
    return render(request, template_name)

@login_required(login_url='login')
def change_password(request):
    template_name = 'templates/account/change_password.html'
    return render(request, template_name)
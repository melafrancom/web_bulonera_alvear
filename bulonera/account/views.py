import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages, auth
from django.contrib.auth.decorators import login_required
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.core.mail import EmailMessage

#IMPORT FROM LOCAL APPS
from .forms import RegistrationForm, UserForm, UserProfileForm
from .models import Account, UserProfile
from cart.models import Cart, CartItem
from cart.views import _cart_id
from orders.models import Order

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
    template_name = 'account/register.html'
    return render(request, template_name, context)


def login(request):
    if request.method == 'POST':
        email = request.POST[email]
        password = request.POST[password]
        
        user = auth.authenticate(email=email, password=password)
        
        if user is not None:
            try:
                cart = Cart.objects.get(cart_id = _cart_id(request))
                is_cart_item_exists = CartItem.objects.filter(cart = cart).exists()
                if is_cart_item_exists:
                    cart_item = CartItem.objects.filter(cart = cart)
                    
                    product_variation = []
                    
                    for item in cart_item:
                        variation = item.variation.all()
                        product_variation.append(list(variation))
                        
                    cart_item = CartItem.objects.filter(user = user)
                    ex_var_list = []
                    id = []
                    
                    for item in cart_item:
                        existing_variation = item.variation.all()
                        ex_var_list.append(list(existing_variation))
                        id.append(item.id)
                        
                    for pr in product_variation:
                        if pr in ex_var_list:
                            index = ex_var_list.index(pr)
                            item_id = id[index]
                            item = CartItem.objects.get(id=item_id)
                            item.quantity += 1
                            item.save()
                        else:
                            cart_item = CartItem.objects.filter(cart = cart)
                            for item in cart_item:
                                item.user = user
                                item.save()
                                
            except:
                pass
            
            auth.login(request, user)
            messages.success(request, 'Has iniciado sesion exitosamente.')
            
            url = request.META.get('HTTP_REFERER')
            try:
                query = request.utils.urlparse(url).query
                params = dict(x.split('=') for x in query.split('&'))
                if 'next' in params:
                    nextPage = params['next']
                    return redirect(nextPage=nextPage)
                
            except:
                return redirect('dashboard')
            
        else:
            messages.error(request, 'Los datos son incorrectos.')
            return redirect('login')
            
    template_name = 'account/login.html'
    return render(request, template_name)


@login_required(login_url='login')
def logout(request):
    auth.logout(request)
    messages.success(request, 'Has cerrado sesion, muchas gracias.')
    return redirect('login')

def activate(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode()
        user = Account._default_manager.get(pk=uid)
    except(TypeError, ValueError, OverflowError, Account.DoesNotExist):
        user = None
        
    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Felicidades, su cuenta está activa.')
        return redirect('login')
    else:
        messages.error(request, 'No se pudo completar la activación de la cuenta.')
        return redirect('register')


@login_required(login_url='login')
def dashboard(request):
    orders = Order.objects.order_by('-created_at').filter(user_id=request.user.id, is_ordered=True)
    orders_count = orders.count()
    
    userprofile = UserProfile.objects.get(user_id=request.user.id)
    
    context = {
        'orders_count': orders_count, 
        'userprofile': userprofile
    }
    
    template_name = 'account/prueba.html'
    return render(request, template_name, context)


def forgotPassword(request):
    template_name = 'account/prueba.html'
    return render(request, template_name)

def resetPassword_validate():
    pass

def reserPassword():
    pass

def my_orders(request):
    orders = Order.objects.filter(user=request.user, is_ordered=True).order_by('-created_at')
    context = {
        'orders' : orders
    }
    template_name = 'account/prueba.html'
    return render(request, template_name, context)

@login_required(login_url='login')
def edit_profile(request):
    userprofile = get_object_or_404(UserProfile, user=request.user)
    if request.method == 'POST':
        user_form = UserForm(request.POST, instance=request.user)
        profile_form = UserProfileForm(request.POST, request.FILE, instance=userprofile)
        
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, 'Su información fue guardada con exito.')
            return redirect('edit_profile')
        else:
            user_form = UserForm(instance = request.user)
            profile_form = UserProfileForm(instance = userprofile)
            
        context = {
            'user_form': user_form,
            'profile_form' : profile_form,
            'userprofile' : userprofile
        }
    template_name = 'account/prueba.html'
    return render(request, template_name, context)

@login_required(login_url='login')
def change_password(request):
    template_name = 'account/prueba.html'
    return render(request, template_name)
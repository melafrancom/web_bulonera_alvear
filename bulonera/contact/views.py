# Create your views here.
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .forms import ContactForm

def contact_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            
            # Si eligieron correo, enviamos el email
            if form.cleaned_data['contact_method'] == 'email':
                send_mail(
                    subject=f"Nuevo contacto: {form.cleaned_data['subject']}",
                    message=f"Nombre: {form.cleaned_data['name']}\nEmail: {form.cleaned_data['email']}\n\nMensaje: {form.cleaned_data['message']}",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.CONTACT_EMAIL],  # Define esto en settings.py
                )
                messages.success(request, "¡Gracias por tu mensaje! Te contactaremos pronto.")
            else:
                # Si eligieron WhatsApp, simplemente mostramos un mensaje
                messages.success(request, "Gracias por elegir contactarnos por WhatsApp. Serás redirigido en breve.")
            
            return redirect(reverse('contact_success'))
    else:
        form = ContactForm()
    
    # Pasar el número de WhatsApp de la empresa al contexto
    whatsapp_number = settings.WHATSAPP_NUMBER  # Define esto en settings.py
    
    return render(request, 'contact/contact.html', {
        'form': form,
        'whatsapp_number': whatsapp_number
    })

def contact_success(request):
    return render(request, 'contact/contact_success.html')
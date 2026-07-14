"""Contact Web Views"""
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages

from contact.web.forms import ContactForm
from contact.services import ContactService

import logging

logger = logging.getLogger(__name__)


def contact_view(request):
    """Vista de formulario de contacto (formulario HTML tradicional)"""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            try:
                # Usar el servicio para crear el contacto
                ContactService.create_contact(
                    name=form.cleaned_data['name'],
                    email=form.cleaned_data['email'],
                    contact_method=form.cleaned_data['contact_method'],
                    subject=form.cleaned_data['subject'],
                    message=form.cleaned_data['message']
                )
                
                # Mensaje de éxito según el método elegido
                if form.cleaned_data['contact_method'] == 'email':
                    messages.success(request, "¡Gracias por tu mensaje! Te contactaremos pronto.")
                else:
                    messages.success(request, "Gracias por elegir contactarnos por WhatsApp. Serás redirigido en breve.")
                
                return redirect(reverse('contact:contact_success'))
                
            except ValueError as e:
                logger.warning(f"Error validando formulario de contacto: {e}")
                messages.error(request, "Error al procesar tu solicitud. Por favor intenta de nuevo.")
            except Exception as e:
                logger.error(f"Error en contact_view: {e}")
                messages.error(request, "Ocurrió un error. Por favor intenta de nuevo más tarde.")
    else:
        form = ContactForm()
    
    # Breadcrumb
    breadcrumb_items = [
        {'name': 'Inicio', 'url': '/'},
        {'name': 'Contacto', 'url': None},
    ]
    
    # Datos para el contexto
    from django.conf import settings
    context = {
        'form': form,
        'whatsapp_number': getattr(settings, 'WHATSAPP_NUMBER', None),
        'breadcrumb_items': breadcrumb_items,
    }
    
    return render(request, 'contact/contact.html', context)


def contact_success(request):
    """Vista de éxito después de enviar contacto"""
    return render(request, 'contact/contact_success.html')

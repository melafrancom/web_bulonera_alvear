"""Contact Web Views"""
import logging
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages
from django.conf import settings

from contact.web.forms import ContactForm
from contact.services import ContactService, ContactRateLimited

logger = logging.getLogger(__name__)


def _get_client_ip(request) -> str:
    """Extrae la IP real del cliente considerando el proxy reverso (OLS / Nginx)."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


def contact_view(request):
    """Vista de formulario de contacto web tradicional."""
    breadcrumb_items = [
        {'name': 'Inicio', 'url': '/'},
        {'name': 'Contacto', 'url': None},
    ]
    canonical_url = request.build_absolute_uri(reverse('contact:contact'))

    if request.method == 'POST':
        client_ip = _get_client_ip(request)

        # 1. Chequeo de Rate Limit (Redis / LocMem)
        try:
            ContactService.check_rate_limit(client_ip)
        except ContactRateLimited:
            messages.error(
                request,
                "Has superado el límite de mensajes permitidos por hora. Por favor intenta más tarde."
            )
            form = ContactForm(request.POST)
            context = {
                'form': form,
                'whatsapp_number': getattr(settings, 'WHATSAPP_NUMBER', None),
                'breadcrumb_items': breadcrumb_items,
                'canonical_url': canonical_url,
            }
            return render(request, 'contact/contact.html', context, status=429)

        # 2. Chequeo de Honeypot Anti-Spam (trampa invisible para bots)
        honeypot_value = request.POST.get('website', '').strip()
        if honeypot_value:
            logger.info("Bot de spam interceptado vía honeypot desde IP: %s", client_ip)
            # Redirección silenciosa a éxito sin persistir ni enviar email
            return redirect(reverse('contact:contact_success'))

        form = ContactForm(request.POST)
        if form.is_valid():
            try:
                ContactService.create_contact(
                    name=form.cleaned_data['name'],
                    email=form.cleaned_data['email'],
                    contact_method=form.cleaned_data['contact_method'],
                    subject=form.cleaned_data['subject'],
                    message=form.cleaned_data['message']
                )

                if form.cleaned_data['contact_method'] == 'email':
                    messages.success(request, "¡Gracias por tu mensaje! Te contactaremos a la brevedad.")
                else:
                    messages.success(request, "¡Gracias por tu consulta! Nos contactaremos contigo por WhatsApp.")

                return redirect(reverse('contact:contact_success'))

            except ValueError as e:
                logger.warning("Error de validación en formulario de contacto: %s", e)
                messages.error(request, f"Error al procesar tu solicitud: {e}")
            except Exception:
                logger.error("Error inesperado en contact_view", exc_info=True)
                messages.error(request, "Ocurrió un error inesperado. Por favor intenta de nuevo más tarde.")
    else:
        form = ContactForm()

    context = {
        'form': form,
        'whatsapp_number': getattr(settings, 'WHATSAPP_NUMBER', None),
        'breadcrumb_items': breadcrumb_items,
        'canonical_url': canonical_url,
    }
    return render(request, 'contact/contact.html', context)


def contact_success(request):
    """Vista de confirmación de éxito tras enviar el formulario de contacto."""
    return render(request, 'contact/contact_success.html')

"""
Orders Web Forms
"""
import re
from django import forms
from orders.models import Order
from orders.utils import validate_cuit, format_cuit, validate_dni


class OrderForm(forms.ModelForm):
    delivery_type = forms.ChoiceField(
        choices=[
            ('pickup', 'Retiro en Local (Av. Alvear 1301)'),
            ('shipping', 'Envío a convenir (Interior / NEA)'),
        ],
        required=True,
        initial=None,
        error_messages={'required': 'Por favor seleccioná una modalidad de entrega.'}
    )
    invoice_type = forms.ChoiceField(
        choices=[
            ('B', 'Consumidor Final (Factura B)'),
            ('A', 'Responsable Inscripto (Factura A)'),
        ],
        required=True,
        initial=None,
        error_messages={'required': 'Por favor seleccioná un tipo de comprobante fiscal.'}
    )

    class Meta:
        model = Order
        fields = [
            'first_name',
            'last_name',
            'phone',
            'email',
            'delivery_type',
            'address_line_1',
            'address_line_2',
            'country',
            'city',
            'state',
            'invoice_type',
            'doc_number',
            'business_name',
            'order_note',
        ]

    def clean_doc_number(self):
        doc = self.cleaned_data.get('doc_number', '')
        if doc:
            return doc.strip()
        return ''

    def clean_business_name(self):
        bname = self.cleaned_data.get('business_name', '')
        if bname:
            return bname.strip()
        return ''

    def clean(self):
        cleaned_data = super().clean()
        delivery_type = cleaned_data.get('delivery_type')
        invoice_type = cleaned_data.get('invoice_type')
        doc_number = cleaned_data.get('doc_number', '').strip()
        business_name = cleaned_data.get('business_name', '').strip()

        # REGLA: Cero fallbacks automáticos. Si el usuario no seleccionó, ChoiceField ya agregó el error.
        
        # Validación condicional de entrega
        if delivery_type == 'shipping':
            if not cleaned_data.get('address_line_1'):
                self.add_error('address_line_1', 'La dirección es obligatoria para envíos al interior/NEA.')
            if not cleaned_data.get('city'):
                self.add_error('city', 'La ciudad o localidad es obligatoria para envíos.')
            if not cleaned_data.get('state'):
                self.add_error('state', 'El código postal es obligatorio para envíos.')
            if not cleaned_data.get('country'):
                cleaned_data['country'] = 'Argentina'
        elif delivery_type == 'pickup':
            # No se inyectan direcciones sintéticas; la dirección queda limpia en BD
            pass

        # Validación condicional fiscal
        if invoice_type == 'A':
            if not business_name:
                self.add_error('business_name', 'La Razón Social es obligatoria para Factura A.')
            if not doc_number:
                self.add_error('doc_number', 'El CUIT es obligatorio para Factura A.')
            elif not validate_cuit(doc_number):
                self.add_error('doc_number', 'El CUIT no es válido. Ingresá 11 dígitos continuos o con guiones canónicos (ej. 30-71234567-8).')
            else:
                cleaned_data['doc_number'] = format_cuit(doc_number)
        elif invoice_type == 'B' and doc_number:
            if not validate_dni(doc_number):
                self.add_error('doc_number', 'El DNI debe tener 7 u 8 dígitos numéricos (ej. 28.123.456 o 28123456).')
            else:
                cleaned_data['doc_number'] = ''.join(c for c in doc_number if '0' <= c <= '9')

        return cleaned_data


class OrderRevocationForm(forms.Form):
    """
    Formulario público para Botón de Arrepentimiento (Disposiciones 954/2025 y 3/2026).
    Campos mínimos: nombre y único dato de contacto (método y valor).
    """
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'autocomplete': 'off',
            'tabindex': '-1',
            'aria-hidden': 'true',
            'style': 'display: none;',
        }),
        label=''
    )

    customer_name = forms.CharField(
        max_length=150,
        required=True,
        label="Nombre y Apellido o Razón Social",
        widget=forms.TextInput(attrs={
            'placeholder': 'Ej: Juan Pérez',
            'class': 'w-full px-4 py-2.5 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-[#1B3A5C]',
            'autocomplete': 'name',
        }),
        error_messages={'required': 'Por favor, ingresá tu nombre o razón social.'}
    )

    contact_method = forms.ChoiceField(
        choices=[
            ('whatsapp', 'WhatsApp / Teléfono'),
            ('email', 'Correo electrónico'),
        ],
        initial='whatsapp',
        required=True,
        label="¿Por qué medio preferís que te contactemos?",
        widget=forms.RadioSelect(attrs={'class': 'text-[#1B3A5C] focus:ring-[#1B3A5C]'})
    )

    contact_value = forms.CharField(
        max_length=150,
        required=True,
        label="Teléfono / WhatsApp o Correo electrónico",
        widget=forms.TextInput(attrs={
            'placeholder': 'Ej: 3624733431 o tu@email.com',
            'class': 'w-full px-4 py-2.5 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-[#1B3A5C]',
        }),
        error_messages={'required': 'Ingresá el dato de contacto para comunicarnos.'}
    )

    order_reference = forms.CharField(
        max_length=100,
        required=False,
        label="Número de pedido o factura (opcional)",
        widget=forms.TextInput(attrs={
            'placeholder': 'Ej: 202610221 (opcional, si lo tenés a mano)',
            'class': 'w-full px-4 py-2.5 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-[#1B3A5C]',
        })
    )

    details = forms.CharField(
        required=False,
        label="Aclaraciones o motivo (opcional)",
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Podés indicar los artículos a devolver o cualquier detalle relevante...',
            'class': 'w-full px-4 py-2.5 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-900 text-slate-900 dark:text-white text-sm focus:outline-none focus:ring-2 focus:ring-[#1B3A5C]',
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('website'):
            raise forms.ValidationError("Solicitud no válida.")

        method = cleaned_data.get('contact_method')
        val = cleaned_data.get('contact_value', '').strip()

        if method == 'email':
            validator = forms.EmailField().clean
            try:
                validator(val)
            except forms.ValidationError:
                self.add_error('contact_value', 'Ingresá una dirección de correo electrónico válida.')
        elif method == 'whatsapp':
            digits = re.sub(r'\D', '', val)
            if len(digits) < 7:
                self.add_error('contact_value', 'Ingresá un número de teléfono o WhatsApp válido con código de área.')

        return cleaned_data
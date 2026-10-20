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
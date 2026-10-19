"""
Orders Web Forms
"""
import re
from django import forms
from orders.models import Order
from orders.utils import validate_cuit, format_cuit, validate_dni


class OrderForm(forms.ModelForm):
    delivery_type = forms.ChoiceField(
        choices=Order.DELIVERY_CHOICES,
        required=False,
        initial='pickup'
    )
    invoice_type = forms.ChoiceField(
        choices=Order.INVOICE_CHOICES,
        required=False,
        initial='B'
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
        delivery_type = cleaned_data.get('delivery_type') or 'pickup'
        invoice_type = cleaned_data.get('invoice_type') or 'B'
        cleaned_data['delivery_type'] = delivery_type
        cleaned_data['invoice_type'] = invoice_type
        doc_number = cleaned_data.get('doc_number', '').strip()
        business_name = cleaned_data.get('business_name', '').strip()

        # Validación condicional de entrega
        if delivery_type == 'shipping':
            if not cleaned_data.get('address_line_1'):
                self.add_error('address_line_1', 'La dirección es obligatoria para envíos.')
            if not cleaned_data.get('city'):
                self.add_error('city', 'La ciudad es obligatoria para envíos.')
            if not cleaned_data.get('state'):
                self.add_error('state', 'El código postal es obligatorio para envíos.')
            if not cleaned_data.get('country'):
                cleaned_data['country'] = 'Argentina'
        elif delivery_type == 'pickup':
            # Asignar valores por defecto del local de Bulonera Alvear
            if not cleaned_data.get('address_line_1'):
                cleaned_data['address_line_1'] = 'Av. Alvear 1301'
            if not cleaned_data.get('city'):
                cleaned_data['city'] = 'Resistencia'
            if not cleaned_data.get('state'):
                cleaned_data['state'] = '3500'
            if not cleaned_data.get('country'):
                cleaned_data['country'] = 'Argentina'

        # Validación condicional fiscal
        if invoice_type == 'A':
            if not business_name:
                self.add_error('business_name', 'La Razón Social es obligatoria para Factura A.')
            if not doc_number:
                self.add_error('doc_number', 'El CUIT es obligatorio para Factura A.')
            elif not validate_cuit(doc_number):
                self.add_error('doc_number', 'El CUIT ingresado no es válido (debe tener 11 dígitos y dígito verificador correcto).')
            else:
                cleaned_data['doc_number'] = format_cuit(doc_number)
        elif invoice_type == 'B' and doc_number:
            if not validate_dni(doc_number):
                self.add_error('doc_number', 'El DNI debe tener 7 u 8 dígitos numéricos.')
            else:
                cleaned_data['doc_number'] = re.sub(r'\D', '', doc_number)

        return cleaned_data
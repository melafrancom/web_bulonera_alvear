from django import forms

#local:
from .models import Order

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['first_name', 'last_name', 'number_phone', 'email', 'address_line_1', 'address_line_2', 'country', 'city', 'state', 'order_note']
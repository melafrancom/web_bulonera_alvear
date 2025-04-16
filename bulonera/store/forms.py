from django import forms
import os

from .models import ReviewRating



class ReviewForm(forms.ModelForm):
    class Meta:
        model = ReviewRating
        fields = ['subject', 'review', 'rating']
        

class ProductImportForm(forms.Form):
    file = forms.FileField(
        label='Seleccionar archivos',
        help_text='Formatos permitidos: Excel (.xlsx), CSV'
    )
    
    def clean_file(self):
        file = self.cleaned_data['file'] 
        ext = os.path.splitext(file.name)[1]
        valid_extensions = ['.xlsx', '.csv']
        
        if ext.lower() not in valid_extensions:
            raise forms.ValidationError('Solo se admiten archivos Excel y CSV.')
        
        return file

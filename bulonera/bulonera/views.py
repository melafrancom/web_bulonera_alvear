from django.shortcuts import render
from store.models import Product

def home(request):
    # obtenemos todos los productos ... Los filtramos por disponibilidad ... Los ordenamos por fecha de creacion.
    products = Product.objects.all().filter(is_available=True).order_by('created_date')
    
    #Creamos un diccionario contexto para almacenar los datos que pasaremos (productos y reseñas).
    context = { 'products': products }
    
    template_name = 'home.html'
    return render(request, template_name)
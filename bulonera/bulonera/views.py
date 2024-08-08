from django.shortcuts import render
from store.models import Product, ReviewRating

def home(request):
    # obtenemos todos los productos ... Los filtramos por disponibilidad ... Los ordenamos por fecha de creacion.
    products = Product.objects.all().filter(is_available=True).order_by('created_date')
    
    for product in products:
        reviews = ReviewRating.objects.filter(product_id=product.id, status=True)
    #Creamos un diccionario contexto para almacenar los datos que pasaremos (productos y reseñas).
    
    context = {
        'products' : products,
        'reviews' : reviews,
    }
    
    template_name = 'home.html'
    return render(request, template_name, context)
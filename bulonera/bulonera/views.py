from django.shortcuts import render
from django.db.models import Sum, Count

from store.models import Product, ReviewRating, ProductSearch, CarouselImage

# En tu archivo views.py principal (puede ser home/views.py o como lo hayas llamado)
from django.shortcuts import render
from store.models import Product, ProductSearch, CarouselImage
from django.db.models import Sum, Count

def home(request):
    # Obtener imágenes activas del carrusel configuradas por el administrador
    carousel_images = CarouselImage.objects.filter(is_active=True).order_by('position')
    
    # Obtener productos más buscados globalmente
    most_searched_products = Product.objects.filter(
        productsearch__isnull=False
    ).annotate(
        total_searches=Sum('productsearch__search_count')
    ).order_by('-total_searches')[:5]
    
    # Obtener productos más buscados por el usuario actual
    user_searched_products = []
    if request.user.is_authenticated:
        user_searched_products = Product.objects.filter(
            productsearch__user=request.user
        ).annotate(
            user_searches=Sum('productsearch__search_count')
        ).order_by('-user_searches')[:5]
    else:
        # Si no está autenticado, usar sesión
        session_key = request.session.session_key
        if session_key:
            user_searched_products = Product.objects.filter(
                productsearch__session_key=session_key
            ).annotate(
                user_searches=Sum('productsearch__search_count')
            ).order_by('-user_searches')[:5]
    
    # obtenemos todos los productos ... Los filtramos por disponibilidad ... Los ordenamos por fecha de creacion.
    products = Product.objects.all().filter(is_available=True).order_by('created_date')
    for product in products:
        reviews = ReviewRating.objects.filter(product_id=product.id, status=True)
    #Creamos un diccionario contexto para almacenar los datos que pasaremos (productos y reseñas).
    context = {
        'carousel_images': carousel_images,
        'most_searched_products': most_searched_products,
        'user_searched_products': user_searched_products,
        'products': products,
        'reviews': reviews,
    }
    
    return render(request, 'home.html', context)


#-------------------- OTRAS VISTAS que no hacen a la funcionalidad. NO NECESARIOS. ------------------------
def location(request):
    template_name = 'others/location.html'
    return render(request, template_name)

def contactUs(request):
    template_name = 'others/contactUs.html'
    return render(request, template_name)

def history(request):
    template_name = 'others/history.html'
    return render(request, template_name)

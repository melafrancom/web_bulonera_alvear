from django.shortcuts import render
from django.db.models import Sum, Count, Q
from math import ceil

#Local
from store.models import Product, ReviewRating, ProductSearch, CarouselImage
from orders.models import OrderProduct, Order
from category.models import Category, SubCategory, FeaturedCategory

def home(request):
    order_products = OrderProduct.objects.all()
    # Obtener imágenes activas del carrusel configuradas por el administrador
    carousel_images = CarouselImage.objects.filter(is_active=True).order_by('position')
    
    # Obtener productos más buscados globalmente
    most_searched_products = Product.objects.filter(is_available=True).order_by('-productsearch__search_count')[:12]
    # Agrupar productos más buscados en grupos de 4
    most_searched_products_groups = [most_searched_products[i:i+4] for i in range(0, len(most_searched_products), 4)]
    
    # Obtener productos más buscados por el usuario actual
    user_searched_products = []
    if request.user.is_authenticated:
        user_searched_products = Product.objects.filter(
            productsearch__user=request.user
        ).annotate(
            user_searches=Sum('productsearch__search_count')
        ).order_by('-user_searches')[:12]
    else:
        # Si no está autenticado, usar sesión
        session_key = request.session.session_key
        if session_key:
            user_searched_products = Product.objects.filter(
                productsearch__session_key=session_key
            ).annotate(
                user_searches=Sum('productsearch__search_count')
            ).order_by('-user_searches')[:12]

    # Agrupar productos buscados por el usuario en grupos de 4
    user_searched_products_groups = [user_searched_products[i:i+4] for i in range(0, len(user_searched_products), 4)]
    
    
    # En lugar de enviar toda la lista de productos, envía los productos ya agrupados
    bestseller_products = Product.objects.filter(
        is_available=True,
        orderproduct__isnull=False
    ).annotate(
        order_count=Sum('orderproduct__quantity')
    ).order_by('-order_count')[:20]
    # Preparar los grupos de 4 productos cada uno
    bestseller_products_groups = [bestseller_products[i:i+4] for i in range(0, len(bestseller_products), 4)]

    # Obtener todas las categorías
    all_categories = Category.objects.all()
    
    # Calcular cantidad total de slides
    total_slides = (
        carousel_images.count() + 
        len(most_searched_products_groups) + 
        len(user_searched_products_groups)
    )
    # Categorías destacadas para los carruseles específicos
    featured_categories = Category.objects.filter(
        featuredcategory__is_active=True
    ).order_by('featuredcategory__position')[:4]  # Limitamos a 4 categorías

    # Obtener los productos más vendidos por cada categoría destacada y agruparlos
    category_products = {}
    for category in featured_categories:
        products = Product.objects.filter(
            category=category, 
            is_available=True,
            orderproduct__isnull=False
        ).annotate(
            total_quantity=Sum('orderproduct__quantity')
        ).order_by('-total_quantity')[:16]  # Limitamos a 16 (4 grupos de 4)
        
        # Agrupamos en bloques de 4
        product_groups = []
        for i in range(0, len(products), 4):
            group = products[i:i+4]
            if group:  # Asegurarse de que el grupo no está vacío
                product_groups.append(group)
        
        category_products[category] = product_groups
    
    context = {
        'carousel_images': carousel_images,
        'bestseller_products': bestseller_products,
        'bestseller_products_groups': bestseller_products_groups,
        'all_categories': all_categories,
        'featured_categories': featured_categories,
        'category_products': category_products,
        'most_searched_products': most_searched_products,
        'user_searched_products': user_searched_products,
        'most_searched_products_groups': most_searched_products_groups,
        'user_searched_products_groups': user_searched_products_groups,
        'total_slides': total_slides,  # Convertir a rango para iterar en el template
    }
    
    return render(request, 'home.html', context)
#-------------------- OTRAS VISTAS que no hacen a la funcionalidad. NO NECESARIOS. ------------------------
def location(request):
    template_name = 'others/location.html'
    return render(request, template_name)

def history(request):
    template_name = 'others/history.html'
    return render(request, template_name)

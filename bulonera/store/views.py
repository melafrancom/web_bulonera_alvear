from django.shortcuts import render, HttpResponse, get_object_or_404, redirect
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.contrib import messages
from django.http import JsonResponse
from django.views.generic import DetailView, ListView
#from django.conf import settings

from bulonera.settings import SITE_URL, CURRENCY
from .models import Product, ReviewRating, ProductGallery, ProductSearch, CarouselImage
from account.models import Account
from category.models import Category, SubCategory
from cart.models import CartItem
from cart.views import _cart_id
from orders.models import OrderProduct
from .forms import ReviewForm
from itertools import chain # Importa chain al principio

# Create your views here.
def store(request, category_slug=None, subcategory_slug=None):
    categories = None
    subcategories = None
    category = None
    subcategory = None

    # Inicializar products_base con todos los productos disponibles
    products_base = Product.objects.filter(is_available=True)
    subcategories = SubCategory.objects.all()  # Inicializar subcategories aquí

    # Obtener los valores de precio min y max del request
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')

    # Obtener productos en oferta para el carrusel
    sale_products = Product.objects.filter(is_on_sale=True, is_available=True)

    # Filtrar por categoría si existe
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)#Obtener las categorias
        products_base = products_base.filter(category=category)
        subcategories = SubCategory.objects.filter(category=category) #Obtener las subcategorias

        # Si estamos en una categoría o subcategoría, filtrar sale_products por esa misma categoría
        if category:
            sale_products = sale_products.filter(category=category)
        if subcategory:
            sale_products = sale_products.filter(subcategories=subcategory)

    # Aplicar filtro de precio si se especificó
    if min_price and max_price:
        try:
            min_price = float(min_price)
            max_price = float(max_price)
            products_base = products_base.filter(price__gte=min_price, price__lte=max_price)
            sale_products = sale_products.filter(price__gte=min_price, price__lte=max_price)
        except ValueError:
            pass  # Si hay un error de conversión, ignoramos el filtro

    # Filtrado por marca
    brand = request.GET.get('brand')
    if brand:
        if brand == 'sin_marca':
            products_base = products_base.filter(brand__isnull=True)
            sale_products = sale_products.filter(brand__isnull=True)
        else:
            products_base = products_base.filter(brand=brand)
            sale_products = sale_products.filter(brand=brand)

    # Separar productos en oferta y productos normales
    sale_products_for_listing = products_base.filter(is_on_sale=True)
    non_sale_products = products_base.filter(is_on_sale=False)
    # Ordenar productos según el criterio seleccionado
    sort_by = request.GET.get('sort_by', 'id')
    if sort_by == 'price_asc':
        sale_products_for_listing = sale_products_for_listing.order_by('price')
        non_sale_products = non_sale_products.order_by('price')
    elif sort_by == 'price_desc':
        sale_products_for_listing = sale_products_for_listing.order_by('-price')
        non_sale_products = non_sale_products.order_by('-price')
    else:
        sale_products_for_listing = sale_products_for_listing.order_by('id')
        non_sale_products = non_sale_products.order_by('id')

    # Combinar los productos en oferta y no en oferta
    products = list(chain(sale_products_for_listing, non_sale_products))

    # Paginación
    paginator = Paginator(products, 30)
    page = request.GET.get('page')
    paged_products = paginator.get_page(page)
    product_count = len(products)

    # Obtener todas las categorías principales para el menú
    main_categories = Category.objects.all()
    categories = Category.objects.prefetch_related('subcategories').all()

    # Obtener marcas únicas
    brands = Product.objects.values_list('brand', flat=True).distinct()
    brands = [brand for brand in brands if brand]  # Eliminar valores nulos o vacíos
    brands.append('sin_marca')  # Agregar la opción "Sin marca"

    # Agrupar productos en oferta para el carrusel (4 por grupo)
    sale_products_groups = [sale_products[i:i+4] for i in range(0, len(sale_products), 4)]

    context = {
        'products': paged_products,
        'product_count': product_count,
        'min_price': min_price,
        'max_price': max_price,
        'sort_by': sort_by,
        'main_categories': main_categories,
        'links': categories,
        'brands': brands,
        'subcategories': subcategories,
        'category_slug': category_slug,
        'current_category': category,
        'current_subcategory': subcategory,
        'sale_products_groups': sale_products_groups,
        'show_sale_carousel': not (category_slug or subcategory_slug),  # Mostrar carrusel solo en la vista principal
    }

    template_name = 'store/store.html'
    return render(request, template_name, context)

def products_by_subcategory(request, category_slug, subcategory_slug):
    try:
        subcategory = SubCategory.objects.get(category__slug=category_slug, slug=subcategory_slug)
        products = Product.objects.filter(
            subcategories=subcategory,
            is_available=True
        ).order_by('id')
        product_count = products.count()
    except Exception as e:
        raise e

    context = {
        'products': products,
        'product_count': products.count(),
        'subcategory': subcategory,
        'subcategories': subcategory.category.subcategories.all(),
    }
    return render(request, 'store/store.html', context)

def product_detail(request, category_slug, product_slug):
    try:
        single_product = Product.objects.get(category__slug=category_slug, slug=product_slug)
        in_cart = CartItem.objects.filter(cart__cart_id=_cart_id(request), product=single_product).exists()
        
        # Get products on sale for carousel (excluding current product)
        sale_products = Product.objects.filter(
            is_on_sale=True, 
            is_available=True
        ).exclude(id=single_product.id)[:5]  # Limit to 5 products
        
    except Exception as e:
        raise e
    
    if request.user.is_authenticated:
        try:
            orderproduct = OrderProduct.objects.filter(user=request.user, product__id=single_product.id).exists()

        except OrderProduct.DoesNotExist:
            orderproduct = None
    else:
        orderproduct = None

    reviews = ReviewRating.objects.filter(product__id=single_product.id, status=True)
    product_gallery = ProductGallery.objects.filter(product_id=single_product.id)

    # Obtener los datos para META PIXEL
    try:
        meta_pixel_data = single_product.get_meta_pixel_data()
    except AttributeError:
        # Fallback si el método no existe o hay error
        site_url = getattr(SITE_URL, '')

        meta_pixel_data = {
            'id': str(single_product.id),
            'title': single_product.name,
            'description': single_product.description if single_product.description else "",
            'availability': 'in stock' if single_product.is_available and single_product.stock > 0 else 'out of stock',
            'condition': getattr(single_product, 'condition', 'new'),
            'price': f"{single_product.price:.2f}",
            'link': f"{site_url}{request.path}",
            'image_link': f"{site_url}{single_product.images.url}" if single_product.images else "",
            'brand': getattr(single_product, 'brand', ""),
        }

    # Obtener la moneda desde settings para el script del META PIXEL
    currency = CURRENCY
    # Determine the display price (regular or sale price)
    display_price = single_product.sale_price if single_product.is_on_sale and single_product.sale_price else single_product.price

        # Update meta_pixel_data price to also use sale price when applicable
    if single_product.is_on_sale and single_product.sale_price:
        meta_pixel_data['price'] = f"{single_product.sale_price:.2f}"
        
    context = {
        'single_product': single_product,
        'price': f"{display_price:.2f}",
        'regular_price': f"{single_product.price:.2f}",
        'in_cart': in_cart,
        'orderproduct': orderproduct,
        'reviews': reviews,
        'product_gallery': product_gallery,
        'meta_pixel_data': meta_pixel_data,
        'CURRENCY': currency,
        'sale_products': sale_products,  # Add sale products to context
    }

    template_name = 'store/product_detail.html'
    return render(request, template_name, context)

def search(request):
    keyword = request.GET['keyword']
    if keyword:
        products = Product.objects.order_by('-created_date').filter(Q(description__icontains=keyword) | Q(name__icontains=keyword))

        # Registrar búsquedas de productos encontrados
        if products.exists() and len(keyword) > 2:  # Solo registrar búsquedas con más de 2 caracteres
            for product in products[:8]:  # Limitar a los primeros 8 resultados
                # Obtener sesión o usuario
                if request.user.is_authenticated:
                    product_search, created = ProductSearch.objects.get_or_create(
                        product=product,
                        user=request.user,
                        defaults={'search_count': 1}
                    )
                    if not created:
                        product_search.search_count += 1
                        product_search.save()
                else:
                    session_key = request.session.session_key
                    if not session_key:
                        request.session.create()
                        session_key = request.session.session_key

                    product_search, created = ProductSearch.objects.get_or_create(
                        product=product,
                        session_key=session_key,
                        defaults={'search_count': 1}
                    )
                    if not created:
                        product_search.search_count += 1
                        product_search.save()
    else:
        # Muestra todos los productos si no hay búsqueda
        products = Product.objects.all().filter(is_available=True)

    product_count = products.count()
    context = {
        'products': products,
        'product_count': product_count,
    }

    template_name = 'store/store.html'
    return render(request, template_name, context)

def submit_review(request, product_id):
    url = request.META.get('HTTP_REFERER')
    if request.method == 'POST':
        try:
            reviews = ReviewRating.objects.get(user__id=request.user.id, product__id=product_id)
            form = ReviewForm(request.POST, instance=reviews)
            form.save()
            messages.success(request, 'Muchas gracias!, tu comentario ha sido actualizado.')
            return redirect(url)

        except ReviewRating.DoesNotExist:
            form = ReviewForm(request.POST)
            if form.is_valid():
                data = ReviewRating()
                data.subject = form.cleaned_data['subject']
                data.rating = form.cleaned_data['rating']
                data.review = form.cleaned_data['review']
                data.ip = request.META.get('REMOTE_ADDR')
                data.product_id = product_id
                data.user_id = request.user.id
                data.save()

                messages.success(request, 'Muchas gracias!, tu comentario ha sido publicado.')
                return redirect(url)


def offers(request):
    """Vista específica para mostrar solo productos en oferta"""
    sale_products = Product.objects.filter(is_on_sale=True, is_available=True)

    # Reutilizamos la lógica de la vista store
    main_categories = Category.objects.all()
    categories = Category.objects.prefetch_related('subcategories').all()

    # Obtener marcas únicas
    brands = Product.objects.values_list('brand', flat=True).distinct()
    brands = [brand for brand in brands if brand]
    brands.append('sin_marca')

    # Paginación
    paginator = Paginator(sale_products, 30)
    page = request.GET.get('page')
    paged_products = paginator.get_page(page)
    product_count = sale_products.count()

    context = {
        'products': paged_products,
        'product_count': product_count,
        'main_categories': main_categories,
        'links': categories,
        'brands': brands,
        'is_offers_page': True,
        'title': 'Ofertas',
    }

    return render(request, 'store/store.html', context)

####### Vistas para META de Facebook y Google Merchant #######

class ProductDetailView(DetailView):# Traemos el detailview de django.views.generic
    model = Product
    template_name = 'store/product_detail.html'
    context_object_name = 'product'

    def get_object(self):
        category_slug = self.kwargs['category_slug']
        product_slug = self.kwargs['product_slug']
        product = Product.objects.get(slug=product_slug, category__slug=category_slug)
        return product

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Agregar datos para META PIXEL
        context['meta_pixel_data'] = self.object.get_meta_pixel_data()
        return context

# Feeds para META PIXEL y Google Merchant
def meta_pixel_product_feed(request):
    products = Product.objects.filter(is_available=True)
    products_data = [product.get_meta_pixel_data() for product in products]
    return JsonResponse({'products': products_data})

def google_merchant_feed(request):
    products = Product.objects.filter(is_available=True)
    products_data = [product.get_merchant_data() for product in products]
    return JsonResponse({'products': products_data})
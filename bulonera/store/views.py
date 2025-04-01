from django.shortcuts import render, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.contrib import messages
from django.http import JsonResponse
from django.views.generic import DetailView, ListView
#from django.conf import settings

from bulonera.settings import SITE_URL, CURRENCY
from .models import Product, ReviewRating, ProductGallery, ProductSearch, CarouselImage
from account.models import Account
from category.models import Category
from cart.models import CartItem
from cart.views import _cart_id
from orders.models import OrderProduct
from .forms import ReviewForm



# Create your views here.
def store(request, category_slug=None):
    categories = None
    products = None
    
    if category_slug != None:
        categories = get_object_or_404(Category, slug=category_slug)
        products = Product.objects.filter(category=categories, is_available=True).order_by('id')
        paginator = Paginator(products, 6)
        page = request.GET.get('page')
        paged_products = paginator.get_page(page)
        product_count = products.count()
    else:
        products = Product.objects.all().filter(is_available=True).order_by('id')
        paginator = Paginator(products, 6)
        page = request.GET.get('page')
        paged_products = paginator.get_page(page)
        product_count = products.count()
        
    context = {
        'products' : paged_products,
        'product_count' : product_count,
    }
        
    template_name = 'store/store.html'
    return render(request, template_name, context)

def product_detail(request, category_slug, product_slug):
    try:
        single_product = Product.objects.get(category__slug=category_slug, slug=product_slug)
        in_cart = CartItem.objects.filter(cart__cart_id=_cart_id(request), product=single_product).exists()
        
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
    
    context = {
        'single_product': single_product,
        'price': f"{single_product.price:.2f}",
        'in_cart': in_cart,
        'orderproduct': orderproduct,
        'reviews': reviews,
        'product_gallery': product_gallery,
        'meta_pixel_data': meta_pixel_data,
        'CURRENCY': currency,
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


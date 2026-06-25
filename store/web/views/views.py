"""Store Web Views"""
import json
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, HttpResponsePermanentRedirect
from django.conf import settings
import csv
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

from store.models import Product, ReviewRating, CarouselImage
from store.web.forms import ReviewForm
from store.services import (
    ProductService, SearchService, ReviewService,
    FAQService, CarouselService, FeedService
)
from category.models import Category, SubCategory
from cart.models import CartItem
from cart.views import _cart_id

logger = logging.getLogger(__name__)

SITE_URL = settings.SITE_URL
CURRENCY = settings.CURRENCY


def store(request, category_slug=None, subcategory_slug=None):
    """Vista principal de la tienda"""
    category = None
    subcategory = None
    
    # Obtener productos base
    products = ProductService.get_all_products()
    subcategories = SubCategory.objects.all()
    
    # Filtrar por categoría si existe
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=category)
        subcategories = SubCategory.objects.filter(category=category)
        
    # Filtrar por subcategoría si existe
    if subcategory_slug:
        subcategory = get_object_or_404(SubCategory, category=category, slug=subcategory_slug)
        products = products.filter(subcategories=subcategory)
    
    # Obtener productos en oferta
    sale_products = ProductService.get_sale_products(category=category, subcategory=subcategory)
    
    # Aplicar filtros
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    brand = request.GET.get('brand')
    sort_by = request.GET.get('sort_by', 'id')
    
    products = ProductService.filter_products(
        products,
        min_price=min_price,
        max_price=max_price,
        brand=brand,
        sort_by=sort_by
    )
    
    sale_products = ProductService.filter_products(
        sale_products,
        min_price=min_price,
        max_price=max_price,
        brand=brand,
        sort_by=sort_by
    )
    
    # Separar productos en oferta y normales
    sale_products_for_listing = products.filter(is_on_sale=True)
    non_sale_products = products.filter(is_on_sale=False)
    
    # Combinar productos (ofertas primero)
    from itertools import chain
    combined_products = list(chain(sale_products_for_listing, non_sale_products))
    
    # Paginar
    page = request.GET.get('page', 1)
    paged_products, product_count = ProductService.get_paginated_products(combined_products, page=page)
    
    # Obtener categorías y marcas
    main_categories = Category.objects.all()
    categories = Category.objects.prefetch_related('subcategories').all()
    brands = ProductService.get_available_brands()
    
    # Agrupar productos en oferta para carrusel
    sale_products_groups = CarouselService.get_sale_products_groups(sale_products)
    
    # Pre-resolver categoría activa y lista de subcategorías para el carrusel de store.html (evita fallos de lookup en template)
    active_category = category
    if not active_category and subcategory:
        active_category = subcategory.category
    
    carousel_subcategories = active_category.subcategories.all() if active_category else None
    
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
        'subcategory_slug': subcategory_slug,
        'current_category': category,
        'category': category,
        'current_subcategory': subcategory,
        'subcategory': subcategory,
        'active_category': active_category,
        'carousel_subcategories': carousel_subcategories,
        'sale_products_groups': sale_products_groups,
        'show_sale_carousel': not (category_slug or subcategory_slug),
        'breadcrumb_items': [
            {'name': 'Inicio', 'url': '/'},
            {'name': category.category_name, 'url': category.get_url()},
            {'name': subcategory.subcategory_name, 'url': None}
        ] if subcategory else ([
            {'name': 'Inicio', 'url': '/'},
            {'name': category.category_name, 'url': None}
        ] if category else [
            {'name': 'Inicio', 'url': '/'},
            {'name': 'Catálogo', 'url': None}
        ]),
    }
    
    return render(request, 'store/store.html', context)


def products_by_subcategory(request, category_slug, subcategory_slug):
    """Vista de productos por subcategoría"""
    try:
        return store(request, category_slug=category_slug, subcategory_slug=subcategory_slug)
    except Exception as e:
        logger.error(f"Error en products_by_subcategory: {e}")
        raise


def redirect_legacy_product(request, category_slug, product_slug):
    """
    Redirige permanentemente URLs legacy a la nueva estructura plana.
    /store/category/<cat>/product/<slug>/ → /store/p/<slug>/
    HTTP 301 (Moved Permanently) para mantener SEO.
    
    Fase 1 - SEO URL Refactoring
    """
    from django.http import HttpResponsePermanentRedirect
    from django.urls import reverse
    
    # Obtener el producto para garantizar que existe antes de redirigir
    try:
        single_product = Product.objects.get(slug=product_slug)
        # Redirigir a la nueva URL plana
        new_url = reverse('store:product_detail', args=[product_slug])
        return HttpResponsePermanentRedirect(new_url)
    except Product.DoesNotExist:
        # Si el producto no existe, devolver 404
        return render(request, 'store/404.html', 
                     {'category_slug': category_slug, 'product_slug': product_slug},
                     status=404)


def product_detail(request, product_slug):
    """
    Vista de detalle de producto - Nueva estructura plana sin category_slug en URL.
    
    Fase 1 - SEO URL Refactoring
    La categoría se extrae de product.category (FK existente).
    """
    try:
        # Obtener producto solo por slug (la categoría viene del FK)
        single_product = Product.objects.get(slug=product_slug)
        
        if not single_product:
            context = {
                'product_slug': product_slug
            }
            return render(request, 'store/404.html', context, status=404)
        
        # Verificar si está en el carrito
        in_cart = CartItem.objects.filter(
            cart__cart_id=_cart_id(request),
            product=single_product
        ).exists()
        
        # Obtener dimensiones disponibles
        dimensions = single_product.get_available_dimensions() if hasattr(single_product, 'get_available_dimensions') else None
        dimension_variants_json = '[]'
        
        if dimensions:
            try:
                variants = ProductService.get_dimension_variants(single_product)
                variants.append(single_product)
                dimension_variants = [
                    {
                        'diameter': str(v.diameter) if hasattr(v, 'diameter') and v.diameter else '',
                        'length': str(v.length) if hasattr(v, 'length') and v.length else '',
                        'url': v.get_url() if hasattr(v, 'get_url') else ''
                    } for v in variants if hasattr(v, 'diameter') or hasattr(v, 'length')
                ]
                dimension_variants_json = json.dumps(dimension_variants)
            except Exception as e:
                logger.error(f'Error processing dimensions for product {single_product.id}: {str(e)}')
        
        # Obtener productos en oferta
        sale_products = ProductService.get_sale_products().exclude(id=single_product.id)[:5]
        
        # Verificar si el usuario puede hacer review
        orderproduct = None
        if request.user.is_authenticated:
            orderproduct = ReviewService.user_can_review(request.user.id, single_product.id)
        
        # Obtener reviews y galería
        reviews = ReviewService.get_product_reviews(single_product.id)
        product_gallery = ProductService.get_product_gallery(single_product.id)
        
        # Obtener datos para META PIXEL
        try:
            meta_pixel_data = single_product.get_meta_pixel_data()
        except AttributeError:
            meta_pixel_data = {
                'id': str(single_product.id),
                'title': single_product.name,
                'description': single_product.description or "",
                'availability': 'in stock' if single_product.is_available and single_product.stock > 0 else 'out of stock',
                'condition': getattr(single_product, 'condition', 'new'),
                'price': f"{single_product.price:.2f}",
                'link': f"{SITE_URL}{request.path}",
                'image_link': f"{SITE_URL}{single_product.images.url}" if single_product.images and single_product.images.name else "",
                'brand': getattr(single_product, 'brand', ""),
            }
        
        # Determinar precio a mostrar
        display_price = single_product.sale_price if single_product.is_on_sale and single_product.sale_price else single_product.price
        
        # Actualizar precio en meta_pixel_data si hay oferta
        if single_product.is_on_sale and single_product.sale_price:
            meta_pixel_data['price'] = f"{single_product.sale_price:.2f}"
        
        # Obtener FAQs del producto
        product_faqs = FAQService.get_product_faqs(single_product)
        
        # Construir breadcrumb_items usando categoria del producto (no del URL)
        breadcrumb_items = [
            {'name': 'Inicio', 'url': '/'},
            {'name': single_product.category.category_name, 'url': single_product.category.get_url()},
            {'name': single_product.name, 'url': None},
        ]
        
        context = {
            'single_product': single_product,
            'in_cart': in_cart,
            'orderproduct': orderproduct,
            'reviews': reviews,
            'product_gallery': product_gallery,
            'meta_pixel_data': meta_pixel_data,
            'price': display_price,
            'CURRENCY': CURRENCY,
            'dimensions': dimensions,
            'dimension_variants_json': dimension_variants_json,
            'sale_products': sale_products,
            'product_faqs': product_faqs,
            'breadcrumb_items': breadcrumb_items,
        }
        
        return render(request, 'store/product_detail.html', context)
    
    except Product.DoesNotExist:
        logger.warning(f'Producto no encontrado: {product_slug}')
        return render(
            request,
            'store/404.html',
            {'product_slug': product_slug},
            status=404
        )
    except Exception as e:
        logger.error(f'Error en product_detail para producto {product_slug}: {str(e)}')
        return render(
            request,
            'store/error.html',
            {'error_message': 'Ha ocurrido un error al cargar el producto'},
            status=500
        )
        display_price = single_product.sale_price if single_product.is_on_sale and single_product.sale_price else single_product.price
        
        # Actualizar precio en meta_pixel_data si hay oferta
        if single_product.is_on_sale and single_product.sale_price:
            meta_pixel_data['price'] = f"{single_product.sale_price:.2f}"
        
        # Obtener FAQs del producto
        product_faqs = FAQService.get_product_faqs(single_product)
        
        # Construir breadcrumb_items (FASE 3.4)
        breadcrumb_items = [
            {'name': 'Inicio', 'url': '/'},
            {'name': single_product.category.category_name, 'url': single_product.category.get_url()},
            {'name': single_product.name, 'url': None},
        ]
        
        context = {
            'single_product': single_product,
            'in_cart': in_cart,
            'orderproduct': orderproduct,
            'reviews': reviews,
            'product_gallery': product_gallery,
            'meta_pixel_data': meta_pixel_data,
            'price': display_price,
            'CURRENCY': CURRENCY,
            'dimensions': dimensions,
            'dimension_variants_json': dimension_variants_json,
            'sale_products': sale_products,
            'product_faqs': product_faqs,
            'breadcrumb_items': breadcrumb_items,
        }
        
        return render(request, 'store/product_detail.html', context)
    
    except Exception as e:
        logger.error(f'Error en product_detail para producto {product_slug}: {str(e)}')
        return render(
            request,
            'store/error.html',
            {'error_message': 'Ha ocurrido un error al cargar el producto'},
            status=500
        )


def search(request):
    """Vista de búsqueda de productos"""
    # Soportar parámetro estándar 'q' además de 'keyword' (retrocompatibilidad)
    keyword = request.GET.get('q', request.GET.get('keyword', ''))
    products = SearchService.search_products(keyword)
    
    # Registrar búsquedas
    if keyword and len(keyword) > 2 and products.exists():
        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        
        SearchService.register_search_results(products, keyword, user, session_key)
    
    context = {
        'products': products,
        'product_count': products.count(),
    }
    
    return render(request, 'store/store.html', context)


@login_required(login_url='account:login')
def submit_review(request, product_id):
    """Vista para enviar review"""
    url = request.META.get('HTTP_REFERER')
    
    if request.method == 'POST':
        # Verificar si ya existe una review
        existing_review = ReviewService.get_user_review(request.user.id, product_id)
        
        if existing_review:
            # Actualizar review existente
            form = ReviewForm(request.POST, instance=existing_review)
            if form.is_valid():
                form.save()
                messages.success(request, 'Muchas gracias! Tu comentario ha sido actualizado.')
                return redirect(url)
        else:
            # Crear nueva review
            form = ReviewForm(request.POST)
            if form.is_valid():
                ReviewService.create_review(
                    user_id=request.user.id,
                    product_id=product_id,
                    subject=form.cleaned_data['subject'],
                    review=form.cleaned_data['review'],
                    rating=form.cleaned_data['rating'],
                    ip=request.META.get('REMOTE_ADDR', '')
                )
                messages.success(request, 'Muchas gracias! Tu comentario ha sido publicado.')
                return redirect(url)
    
    return redirect(url)


def offers(request):
    """Vista de productos en oferta"""
    sale_products = ProductService.get_sale_products()
    
    # Obtener categorías y marcas
    main_categories = Category.objects.all()
    categories = Category.objects.prefetch_related('subcategories').all()
    brands = ProductService.get_available_brands()
    
    # Paginar
    page = request.GET.get('page', 1)
    paged_products, product_count = ProductService.get_paginated_products(sale_products, page=page)
    
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


def faq(request):
    """Vista de FAQs generales"""
    faq_categories = FAQService.get_general_faqs()
    
    context = {
        'faq_categories': faq_categories,
        'meta_title': 'Preguntas Frecuentes | Bulonera Alvear',
        'meta_description': 'Preguntas frecuentes sobre envíos, pagos, productos y más en Bulonera Alvear'
    }
    
    return render(request, 'store/faq.html', context)


def facebook_feed(request):
    """Feed CSV para Facebook"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="facebook_products.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['id', 'title', 'description', 'availability', 'condition', 'price', 'link', 'image_link', 'brand'])
    
    feed_data = FeedService.get_facebook_feed_data()
    for data in feed_data:
        writer.writerow([
            data.get('id'),
            data.get('title'),
            data.get('description'),
            data.get('availability'),
            data.get('condition'),
            data.get('price'),
            data.get('link'),
            data.get('image_link'),
            data.get('brand'),
        ])
    
    return response


def google_merchant_feed(request):
    """Feed XML para Google Merchant"""
    try:
        rss = Element('rss', version="2.0", attrib={'xmlns:g': "http://base.google.com/ns/1.0"})
        channel = SubElement(rss, 'channel')
        SubElement(channel, 'title').text = "Bulonera Alvear Productos"
        SubElement(channel, 'link').text = SITE_URL
        SubElement(channel, 'description').text = "Feed de productos para Google Merchant Center"
        
        feed_data = FeedService.get_google_merchant_feed_data()
        for data in feed_data:
            item = SubElement(channel, 'item')
            SubElement(item, 'g:id').text = str(data.get('code', ''))
            SubElement(item, 'title').text = data.get('title', '')
            SubElement(item, 'description').text = data.get('description', '')
            SubElement(item, 'link').text = data.get('link', '')
            SubElement(item, 'g:image_link').text = data.get('image_link', '')
            SubElement(item, 'g:availability').text = data.get('availability', '')
            SubElement(item, 'g:price').text = data.get('price', '')
            SubElement(item, 'g:brand').text = data.get('brand', '')
            SubElement(item, 'g:condition').text = data.get('condition', '')
            if data.get('gtin'):
                SubElement(item, 'g:gtin').text = data['gtin']
            if data.get('mpn'):
                SubElement(item, 'g:mpn').text = data['mpn']
            if data.get('google_product_category'):
                SubElement(item, 'g:google_product_category').text = data['google_product_category']
        
        xml_str = tostring(rss, encoding='utf-8')
        pretty_xml = parseString(xml_str).toprettyxml(indent="  ")
        return HttpResponse(pretty_xml, content_type='application/xml')
    except Exception as e:
        logger.error(f"Error generando feed de Google Merchant: {e}")
        return HttpResponse(f"Error: {e}", content_type="text/plain", status=500)


__all__ = [
    'store',
    'products_by_subcategory',
    'product_detail',
    'search',
    'submit_review',
    'offers',
    'faq',
    'facebook_feed',
    'google_merchant_feed',
]

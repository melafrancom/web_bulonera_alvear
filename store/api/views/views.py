"""Store API Views"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.http import HttpResponse
import logging
import csv
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

from store.models import Product, ReviewRating, FAQ, FAQCategory, CarouselImage
from store.api.serializers import (
    ProductListSerializer, ProductDetailSerializer,
    ReviewRatingSerializer, CreateReviewSerializer, UpdateReviewSerializer,
    FAQSerializer, FAQCategorySerializer, CarouselImageSerializer,
    SearchSerializer, ProductFilterSerializer
)
from store.services import (
    ProductService, SearchService, ReviewService,
    FAQService, CarouselService, FeedService
)

logger = logging.getLogger(__name__)


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para productos"""
    permission_classes = [AllowAny]
    lookup_field = 'slug'
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ProductDetailSerializer
        return ProductListSerializer
    
    def get_queryset(self):
        return ProductService.get_all_products()
    
    def list(self, request):
        """GET /api/store/products/"""
        filter_serializer = ProductFilterSerializer(data=request.query_params)
        if not filter_serializer.is_valid():
            return Response(filter_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        filters = filter_serializer.validated_data
        products = ProductService.get_all_products()
        
        # Aplicar filtros
        products = ProductService.filter_products(
            products,
            min_price=filters.get('min_price'),
            max_price=filters.get('max_price'),
            brand=filters.get('brand'),
            sort_by=filters.get('sort_by', 'id')
        )
        
        # Paginar
        paged_products, total_count = ProductService.get_paginated_products(
            products,
            page=filters.get('page', 1)
        )
        
        serializer = self.get_serializer(paged_products, many=True)
        return Response({
            'count': total_count,
            'results': serializer.data,
            'page': filters.get('page', 1),
            'total_pages': paged_products.paginator.num_pages if hasattr(paged_products, 'paginator') else 1
        })
    
    def retrieve(self, request, slug=None):
        """GET /api/v1/store/products/{slug}/"""
        try:
            product = Product.objects.get(slug=slug)
            serializer = self.get_serializer(product)
            return Response(serializer.data)
        except Product.DoesNotExist:
            return Response({'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """GET /api/store/products/by_category/?slug={category_slug}"""
        category_slug = request.query_params.get('slug')
        if not category_slug:
            return Response({'error': 'Se requiere slug de categoría'}, status=status.HTTP_400_BAD_REQUEST)
        
        products = ProductService.get_products_by_category(category_slug)
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_subcategory(self, request):
        """GET /api/store/products/by_subcategory/?slug={subcategory_slug}"""
        subcategory_slug = request.query_params.get('slug')
        if not subcategory_slug:
            return Response({'error': 'Se requiere slug de subcategoría'}, status=status.HTTP_400_BAD_REQUEST)
        
        products = ProductService.get_products_by_subcategory(subcategory_slug)
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def on_sale(self, request):
        """GET /api/store/products/on_sale/"""
        products = ProductService.get_sale_products()
        serializer = self.get_serializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def reviews(self, request, slug=None):
        """GET /api/v1/store/products/{slug}/reviews/"""
        try:
            product = Product.objects.get(slug=slug)
            reviews = ReviewService.get_product_reviews(product.id)
            serializer = ReviewRatingSerializer(reviews, many=True)
            return Response(serializer.data)
        except Product.DoesNotExist:
            return Response({'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['get'])
    def faqs(self, request, slug=None):
        """GET /api/v1/store/products/{slug}/faqs/"""
        try:
            product = Product.objects.get(slug=slug)
            faqs = FAQService.get_product_faqs(product)
            serializer = FAQSerializer(faqs, many=True)
            return Response(serializer.data)
        except Product.DoesNotExist:
            return Response({'error': 'Producto no encontrado'}, status=status.HTTP_404_NOT_FOUND)


class SearchViewSet(viewsets.ViewSet):
    """ViewSet para búsqueda de productos"""
    permission_classes = [AllowAny]
    
    def list(self, request):
        """GET /api/v1/store/search/?keyword={keyword}"""
        keyword = request.query_params.get('keyword', '')
        products = SearchService.search_products(keyword)
        
        # Registrar búsquedas
        if keyword and len(keyword) > 2:
            user = request.user if request.user.is_authenticated else None
            session_key = request.session.session_key
            if not session_key:
                request.session.create()
                session_key = request.session.session_key
            
            SearchService.register_search_results(products, keyword, user, session_key)
        
        serializer = ProductListSerializer(products, many=True)
        return Response({
            'keyword': keyword,
            'count': products.count(),
            'results': serializer.data
        })


class ReviewViewSet(viewsets.ViewSet):
    """ViewSet para reviews"""
    permission_classes = [IsAuthenticated]
    
    def create(self, request):
        """POST /api/v1/store/reviews/"""
        product_id = request.data.get('product_id')
        if not product_id:
            return Response({'error': 'Se requiere product_id'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Verificar si el usuario puede hacer review
        if not ReviewService.user_can_review(request.user.id, product_id):
            return Response({
                'error': 'Debes haber comprado este producto para dejar una review'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Verificar si ya existe una review
        existing_review = ReviewService.get_user_review(request.user.id, product_id)
        
        if existing_review:
            # Actualizar review existente
            serializer = UpdateReviewSerializer(data=request.data)
            if serializer.is_valid():
                updated_review = ReviewService.update_review(
                    existing_review,
                    subject=serializer.validated_data.get('subject'),
                    review_text=serializer.validated_data.get('review'),
                    rating=serializer.validated_data.get('rating')
                )
                return Response({
                    'message': 'Review actualizada exitosamente',
                    'review': ReviewRatingSerializer(updated_review).data
                })
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Crear nueva review
            serializer = CreateReviewSerializer(data=request.data)
            if serializer.is_valid():
                review = ReviewService.create_review(
                    user_id=request.user.id,
                    product_id=product_id,
                    subject=serializer.validated_data['subject'],
                    review=serializer.validated_data['review'],
                    rating=serializer.validated_data['rating'],
                    ip=request.META.get('REMOTE_ADDR', '')
                )
                return Response({
                    'message': 'Review creada exitosamente',
                    'review': ReviewRatingSerializer(review).data
                }, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FAQViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para FAQs"""
    permission_classes = [AllowAny]
    serializer_class = FAQCategorySerializer
    
    def get_queryset(self):
        return FAQService.get_general_faqs()
    
    @action(detail=False, methods=['get'])
    def by_category(self, request):
        """GET /api/store/faqs/by_category/?category_id={id}"""
        category_id = request.query_params.get('category_id')
        if not category_id:
            return Response({'error': 'Se requiere category_id'}, status=status.HTTP_400_BAD_REQUEST)
        
        faqs = FAQService.get_faqs_by_category(category_id)
        serializer = FAQSerializer(faqs, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def by_subcategory(self, request):
        """GET /api/store/faqs/by_subcategory/?subcategory_id={id}"""
        subcategory_id = request.query_params.get('subcategory_id')
        if not subcategory_id:
            return Response({'error': 'Se requiere subcategory_id'}, status=status.HTTP_400_BAD_REQUEST)
        
        faqs = FAQService.get_faqs_by_subcategory(subcategory_id)
        serializer = FAQSerializer(faqs, many=True)
        return Response(serializer.data)


class CarouselViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para carrusel"""
    permission_classes = [AllowAny]
    serializer_class = CarouselImageSerializer
    
    def get_queryset(self):
        return CarouselService.get_active_carousel_images()


class FeedViewSet(viewsets.ViewSet):
    """ViewSet para feeds (Facebook, Google Merchant)"""
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['get'])
    def facebook_csv(self, request):
        """GET /api/store/feeds/facebook_csv/"""
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
    
    @action(detail=False, methods=['get'])
    def google_merchant_xml(self, request):
        """GET /api/store/feeds/google_merchant_xml/"""
        try:
            from django.conf import settings
            site_url = settings.SITE_URL
            
            rss = Element('rss', version="2.0", attrib={'xmlns:g': "http://base.google.com/ns/1.0"})
            channel = SubElement(rss, 'channel')
            SubElement(channel, 'title').text = "Bulonera Alvear Productos"
            SubElement(channel, 'link').text = site_url
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
    'ProductViewSet',
    'SearchViewSet',
    'ReviewViewSet',
    'FAQViewSet',
    'CarouselViewSet',
    'FeedViewSet',
]

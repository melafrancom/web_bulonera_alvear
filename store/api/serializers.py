"""Store API Serializers"""
from rest_framework import serializers
from store.models import (
    Product, ReviewRating, ProductGallery, Variation,
    CarouselImage, FAQ, FAQCategory
)
from category.models import Category, SubCategory


class CategorySimpleSerializer(serializers.ModelSerializer):
    """Serializer simple para categoría"""
    class Meta:
        model = Category
        fields = ['id', 'category_name', 'slug']


class SubCategorySimpleSerializer(serializers.ModelSerializer):
    """Serializer simple para subcategoría"""
    class Meta:
        model = SubCategory
        fields = ['id', 'subcategory_name', 'slug']


class ProductGallerySerializer(serializers.ModelSerializer):
    """Serializer para galería de productos"""
    image_urls = serializers.SerializerMethodField()
    
    class Meta:
        model = ProductGallery
        fields = ['id', 'image', 'alt', 'image_urls']
    
    def get_image_urls(self, obj):
        return obj.get_image_urls


class VariationSerializer(serializers.ModelSerializer):
    """Serializer para variaciones de productos"""
    class Meta:
        model = Variation
        fields = ['id', 'variation_category', 'variation_value', 'is_active']


class ProductListSerializer(serializers.ModelSerializer):
    """Serializer para listado de productos"""
    category = CategorySimpleSerializer(read_only=True)
    average_review = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    image_urls = serializers.SerializerMethodField()
    display_price = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'code', 'name', 'slug', 'price', 'sale_price', 'is_on_sale',
            'discount_percentage', 'stock', 'is_available', 'category',
            'images', 'image_urls', 'image_alt', 'brand', 'average_review',
            'review_count', 'display_price', 'created_date'
        ]
    
    def get_average_review(self, obj):
        return obj.averageReview()
    
    def get_review_count(self, obj):
        return obj.countReview()
    
    def get_image_urls(self, obj):
        return obj.get_image_urls
    
    def get_display_price(self, obj):
        if obj.is_on_sale and obj.sale_price:
            return obj.sale_price
        return obj.price


class ProductDetailSerializer(serializers.ModelSerializer):
    """Serializer detallado para producto"""
    category = CategorySimpleSerializer(read_only=True)
    subcategories = SubCategorySimpleSerializer(many=True, read_only=True)
    gallery = ProductGallerySerializer(source='productgallery_set', many=True, read_only=True)
    average_review = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    image_urls = serializers.SerializerMethodField()
    display_price = serializers.SerializerMethodField()
    dimensions = serializers.SerializerMethodField()
    meta_pixel_data = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = [
            'id', 'code', 'name', 'slug', 'description', 'price', 'sale_price',
            'is_on_sale', 'discount_percentage', 'stock', 'is_available',
            'category', 'subcategories', 'images', 'image_urls', 'image_alt',
            'brand', 'condition', 'diameter', 'length', 'norm', 'grade',
            'material', 'colour', 'type', 'form', 'thread_formats', 'origin',
            'average_review', 'review_count', 'gallery', 'display_price',
            'dimensions', 'meta_pixel_data', 'created_date', 'modified_date',
            'meta_title', 'meta_description', 'meta_keywords'
        ]
    
    def get_average_review(self, obj):
        return obj.averageReview()
    
    def get_review_count(self, obj):
        return obj.countReview()
    
    def get_image_urls(self, obj):
        return obj.get_image_urls
    
    def get_display_price(self, obj):
        if obj.is_on_sale and obj.sale_price:
            return obj.sale_price
        return obj.price
    
    def get_dimensions(self, obj):
        if hasattr(obj, 'get_available_dimensions'):
            return obj.get_available_dimensions()
        return None
    
    def get_meta_pixel_data(self, obj):
        try:
            return obj.get_meta_pixel_data()
        except Exception:
            return None


class ReviewRatingSerializer(serializers.ModelSerializer):
    """Serializer para reviews"""
    user_name = serializers.SerializerMethodField()
    
    class Meta:
        model = ReviewRating
        fields = [
            'id', 'product', 'user', 'user_name', 'subject', 'review',
            'rating', 'status', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def get_user_name(self, obj):
        return obj.user.full_name() if obj.user else 'Anónimo'


class CreateReviewSerializer(serializers.Serializer):
    """Serializer para crear review"""
    subject = serializers.CharField(max_length=100)
    review = serializers.CharField(max_length=500)
    rating = serializers.FloatField(min_value=1.0, max_value=5.0)


class UpdateReviewSerializer(serializers.Serializer):
    """Serializer para actualizar review"""
    subject = serializers.CharField(max_length=100, required=False)
    review = serializers.CharField(max_length=500, required=False)
    rating = serializers.FloatField(min_value=1.0, max_value=5.0, required=False)


class FAQSerializer(serializers.ModelSerializer):
    """Serializer para FAQs"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    subcategory_name = serializers.CharField(source='subcategory.subcategory_name', read_only=True)
    
    class Meta:
        model = FAQ
        fields = [
            'id', 'category', 'category_name', 'subcategory', 'subcategory_name',
            'question', 'answer', 'order', 'is_active'
        ]


class FAQCategorySerializer(serializers.ModelSerializer):
    """Serializer para categorías de FAQ"""
    faqs = FAQSerializer(many=True, read_only=True)
    
    class Meta:
        model = FAQCategory
        fields = ['id', 'name', 'order', 'faqs']


class CarouselImageSerializer(serializers.ModelSerializer):
    """Serializer para imágenes del carrusel"""
    image_urls = serializers.SerializerMethodField()
    product_name = serializers.CharField(source='product.name', read_only=True)
    
    class Meta:
        model = CarouselImage
        fields = [
            'id', 'title', 'image', 'image_urls', 'description', 'url',
            'product', 'product_name', 'position', 'is_active'
        ]
    
    def get_image_urls(self, obj):
        return obj.get_image_urls


class SearchSerializer(serializers.Serializer):
    """Serializer para búsqueda"""
    keyword = serializers.CharField(required=True, min_length=1)


class ProductFilterSerializer(serializers.Serializer):
    """Serializer para filtros de productos"""
    min_price = serializers.FloatField(required=False, min_value=0)
    max_price = serializers.FloatField(required=False, min_value=0)
    brand = serializers.CharField(required=False, allow_blank=True)
    sort_by = serializers.ChoiceField(
        choices=['id', 'price_asc', 'price_desc'],
        required=False,
        default='id'
    )
    page = serializers.IntegerField(required=False, default=1, min_value=1)


__all__ = [
    'CategorySimpleSerializer',
    'SubCategorySimpleSerializer',
    'ProductGallerySerializer',
    'VariationSerializer',
    'ProductListSerializer',
    'ProductDetailSerializer',
    'ReviewRatingSerializer',
    'CreateReviewSerializer',
    'UpdateReviewSerializer',
    'FAQSerializer',
    'FAQCategorySerializer',
    'CarouselImageSerializer',
    'SearchSerializer',
    'ProductFilterSerializer',
]

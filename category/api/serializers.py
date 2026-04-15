"""Category API Serializers"""
from rest_framework import serializers
from category.models import Category, SubCategory, FeaturedCategory


class SubCategorySerializer(serializers.ModelSerializer):
    """Serializer para SubCategory"""
    category_name = serializers.CharField(source='category.category_name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    
    class Meta:
        model = SubCategory
        fields = ['id', 'subcategory_name', 'slug', 'category', 'category_name', 
                  'category_slug', 'image']
        read_only_fields = ['id']


class CategorySerializer(serializers.ModelSerializer):
    """Serializer para Category con subcategorías anidadas"""
    subcategories = SubCategorySerializer(many=True, read_only=True)
    subcategory_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'category_name', 'slug', 'description', 'cat_image', 
                  'subcategories', 'subcategory_count']
        read_only_fields = ['id']
    
    def get_subcategory_count(self, obj):
        """Cuenta las subcategorías de esta categoría"""
        return obj.subcategories.count()


class CategoryListSerializer(serializers.ModelSerializer):
    """Serializer simplificado para listado de categorías (sin subcategorías)"""
    subcategory_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = ['id', 'category_name', 'slug', 'description', 'cat_image', 
                  'subcategory_count']
        read_only_fields = ['id']
    
    def get_subcategory_count(self, obj):
        """Cuenta las subcategorías de esta categoría"""
        return obj.subcategories.count() if hasattr(obj, 'subcategories') else 0


class FeaturedCategorySerializer(serializers.ModelSerializer):
    """Serializer para FeaturedCategory"""
    category = CategoryListSerializer(read_only=True)
    
    class Meta:
        model = FeaturedCategory
        fields = ['id', 'category', 'position', 'is_active']
        read_only_fields = ['id']

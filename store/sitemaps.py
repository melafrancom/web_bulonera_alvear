"""
Sitemaps for Store app
Generates dynamic sitemap.xml for products and categories
"""
from django.contrib.sitemaps import Sitemap
from store.models import Product
from category.models import Category


class ProductSitemap(Sitemap):
    """Sitemap for products"""
    changefreq = 'weekly'
    priority = 0.8
    protocol = 'https'

    def items(self):
        return Product.objects.filter(is_available=True).select_related('category')

    def lastmod(self, obj):
        return obj.modified_date

    def location(self, obj):
        return obj.get_url()


class CategorySitemap(Sitemap):
    """Sitemap for categories"""
    changefreq = 'monthly'
    priority = 0.6
    protocol = 'https'

    def items(self):
        return Category.objects.all()

    def location(self, obj):
        return obj.get_url()


class SubCategorySitemap(Sitemap):
    """Sitemap for subcategories"""
    changefreq = 'monthly'
    priority = 0.5
    protocol = 'https'

    def items(self):
        from category.models import SubCategory
        return SubCategory.objects.all().select_related('category')

    def lastmod(self, obj):
        return getattr(obj, 'modified_date', obj.category.modified_date) if hasattr(obj, 'modified_date') else None

    def location(self, obj):
        return obj.get_url()

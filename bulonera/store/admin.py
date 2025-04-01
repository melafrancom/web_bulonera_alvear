from django.contrib import admin
from .models import Product, Variation, ReviewRating, ProductGallery, CarouselImage, ProductSearch
import admin_thumbnails


@admin_thumbnails.thumbnail('image')
class ProductGalleryInLine(admin.TabularInline):
    model = ProductGallery
    extra = 1


class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'stock', 'category', 'modified_date', 'is_available')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductGalleryInLine]


class VariationAdmin(admin.ModelAdmin):
    list_display = ('product', 'variation_category', 'variation_value', 'is_active')
    list_editable = ('is_active',)
    list_filter = ('product', 'variation_category', 'variation_value', 'is_active')



# Register your models here.
admin.site.register(Product, ProductAdmin)
admin.site.register(Variation, VariationAdmin)
admin.site.register(ReviewRating)
admin.site.register(ProductGallery)


##NO HACE A LAS FUNCIONALIDADES PRINCIPALES DE LA PÁGINA:

class CarouselImageAdmin(admin.ModelAdmin):
    list_display = ('title', 'product', 'position', 'is_active', 'created_date')
    list_editable = ('position', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title', 'product__name')

admin.site.register(CarouselImage, CarouselImageAdmin)

# Si quieres ver las estadísticas de búsqueda en el admin
class ProductSearchAdmin(admin.ModelAdmin):
    list_display = ('product', 'search_count', 'user', 'updated_at')
    list_filter = ('created_at',)
    search_fields = ('product__name', 'user__email')
    readonly_fields = ('product', 'user', 'session_key', 'search_count', 'created_at', 'updated_at')

admin.site.register(ProductSearch, ProductSearchAdmin)

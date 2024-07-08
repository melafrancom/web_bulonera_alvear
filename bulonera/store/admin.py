from django.contrib import admin
from .models import Product, ProductAdmin, Variation, VariationAdmin, ReviewRating, ProductGallery

# Register your models here.
admin.site.register(Product, ProductAdmin)
admin.site.register(Variation, VariationAdmin)
admin.site.register(ReviewRating)
admin.site.register(ProductGallery)



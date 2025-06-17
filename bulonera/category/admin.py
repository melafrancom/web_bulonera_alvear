from django.contrib import admin

#local
from .models import Category, SubCategory, FeaturedCategory

class SubCategoryInline(admin.TabularInline):
    model = SubCategory
    prepopulated_fields = {'slug': ('subcategory_name',)}
    extra = 1

class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('category_name',)}
    list_display = ('category_name', 'slug')
    inlines = [SubCategoryInline]

class SubCategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('subcategory_name',)}
    list_display = ('subcategory_name', 'category', 'slug', 'image')
    list_filter = ('category',)
    

class FeaturedCategoryAdmin(admin.ModelAdmin):
    list_display = ('category', 'position', 'is_active')
    list_editable = ('position', 'is_active')
    list_filter = ('is_active',)

admin.site.register(Category, CategoryAdmin)
admin.site.register(SubCategory, SubCategoryAdmin)
admin.site.register(FeaturedCategory, FeaturedCategoryAdmin)



from django.contrib import admin

#local
from .models import Category, SubCategory

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
    list_display = ('subcategory_name', 'category', 'slug')
    list_filter = ('category',)

admin.site.register(Category, CategoryAdmin)
admin.site.register(SubCategory, SubCategoryAdmin)
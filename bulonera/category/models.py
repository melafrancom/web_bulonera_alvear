from django.db import models
from django.urls import reverse

# Create your models here.
# Create your models here.
class Category(models.Model):
    category_name = models.CharField(max_length=20, unique=True)
    description = models.CharField(max_length=255, blank=True)
    slug = models.CharField(max_length=100, unique=True)
    cat_image = models.ImageField(upload_to='photos/categories', blank=True)
    parent = models.ForeignKey('self', null=True, blank=True, related_name='children', on_delete=models.CASCADE)
    
    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
    
    def get_subcategories(self):
        return self.children.all()
        
    def get_url(self):
        return reverse('products_by_category', args=[self.slug])
    
    def __str__(self):
        return self.category_name
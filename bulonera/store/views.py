from django.shortcuts import render, HttpResponse
from .models import Product

# Create your views here.
def store(request):
    
    template_name = 'home.html'
    return render(request, template_name)

def product_detail(request, category_slug, product_slug):
    
    template_name = 'product_detail.html'
    return render(request, template_name)

def search(request):
    template_name = 'home.html'
    return render(request, template_name)


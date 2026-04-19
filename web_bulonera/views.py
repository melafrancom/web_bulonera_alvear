from django.shortcuts import render
from django.db.models import Sum, Count, Q
from django.conf import settings
from math import ceil
from django.http import HttpResponse

SITE_URL = settings.SITE_URL
from store.models import Product, ReviewRating, ProductSearch, CarouselImage
from orders.models import OrderProduct, Order
from category.models import Category, SubCategory, FeaturedCategory

def home(request):
    """
    Vista Home refactorizada con soporte para secciones dinámicas.
    Toda la lógica de generación de contenido está en HomeSectionService.
    """
    from store.models import CarouselImage
    from store.services import HomeSectionService
    from category.models import Category

    # Hero: se mantiene con CarouselImage (modelo existente)
    carousel_images = CarouselImage.objects.filter(is_active=True).order_by('position')

    # Secciones dinámicas
    sections = HomeSectionService.get_active_sections()
    enriched_sections = []
    for section in sections:
        enriched_sections.append({
            'section': section,
            'data': HomeSectionService.get_section_context(section, request),
        })

    context = {
        'carousel_images': carousel_images,
        'carousel_count': carousel_images.count(),
        'sections': enriched_sections,
        'all_categories': Category.objects.all(),
    }
    return render(request, 'home.html', context)



#-------------------- OTRAS VISTAS que no hacen a la funcionalidad. NO NECESARIOS. ------------------------
def returnPolicy(request):
    template_name = 'others/return_policy.html'
    return render(request, template_name)

def termsAndConditions(request):
    template_name = 'others/terms_and_conditions.html'
    return render(request, template_name)

def privacyAndwarranty(request):
    template_name = 'others/privacy_and_warranty.html'
    return render(request, template_name)

def location(request):
    template_name = 'others/location.html'
    return render(request, template_name)

def history(request):
    template_name = 'others/history.html'
    return render(request, template_name)

def offline(request):
    """Vista para la página offline de la PWA"""
    template_name = 'others/offline.html'
    return render(request, template_name)


#-------------------- OTRAS VISTAS que no hacen a la funcionalidad. NO NECESARIOS. SITEMAPS AND ROBOTS ------------------------
def robots_txt(request):
    """
    Robots.txt view with specific User-Agent rules (FASE 3.2 — Auditoría SEO)
    Disallow admin, api, cart, orders
    Permite explícitamente Googlebot, Bingbot, Facebookexternalhit, Twitterbot
    """
    lines = [
        # Googlebot explicit rules
        "User-Agent: Googlebot",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /api/",
        "Disallow: /cart/",
        "Disallow: /orders/",
        "Disallow: /account/dashboard/",
        "",
        # Bingbot explicit rules
        "User-Agent: Bingbot",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /api/",
        "Disallow: /cart/",
        "Disallow: /orders/",
        "Disallow: /account/dashboard/",
        "",
        # Meta/Facebook crawler
        "User-Agent: Facebookexternalhit",
        "Allow: /",
        "",
        # Twitter crawler
        "User-Agent: Twitterbot",
        "Allow: /",
        "",
        # Default (catch-all)
        "User-Agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /api/",
        "Disallow: /cart/",
        "Disallow: /orders/",
        "Disallow: /account/dashboard/",
        "",
        f"Sitemap: {SITE_URL}/sitemap.xml",
        "",
        f"Llms-Txt: {SITE_URL}/llms.txt"
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def llms_txt(request):
    """
    Vista dinámica que genera el archivo llms.txt según la especificación llmstxt.org.
    Incluye información del negocio, categorías y páginas principales.
    """
    from category.models import Category
    
    categories = Category.objects.all()
    lines = [
        "# Bulonera Alvear",
        "",
        "> Ferretería industrial online en Resistencia, Chaco, Argentina. "
        "Venta de bulonería (tornillos, tuercas, pernos, arandelas), "
        "herramientas y materiales eléctricos. Envíos a todo el país.",
        "",
        "- Nombre comercial: Bulonera Alvear",
        "- Ubicación: Av. Alvear 1301, Resistencia, Chaco, Argentina",
        "- Tipo de negocio: Ferretería industrial (B2C y B2B)",
        "- Moneda: ARS (Peso Argentino)",
        "",
        "## Páginas principales",
        f"- [Catálogo completo]({SITE_URL}/store/): Todos los productos disponibles con precios y stock",
        f"- [Ofertas]({SITE_URL}/store/offers/): Productos en promoción",
        f"- [Contacto]({SITE_URL}/contact/): Formulario de contacto y datos de la empresa",
        f"- [Ubicación]({SITE_URL}/location/): Mapa y dirección física",
        f"- [Historia]({SITE_URL}/history/): Historia de la empresa",
        f"- [Política de devolución]({SITE_URL}/return-policy/): Condiciones de devolución",
        f"- [Términos y condiciones]({SITE_URL}/terms-and-conditions/): Términos legales",
        "",
        "## Categorías de productos",
    ]
    
    for cat in categories:
        lines.append(
            f"- [{cat.category_name}]({SITE_URL}/store/category/{cat.slug}/): "
            f"Productos de {cat.category_name.lower()}"
        )
    
    lines.extend([
        "",
        "## Optional",
        f"- [Sitemap XML]({SITE_URL}/sitemap.xml): Mapa del sitio para indexación",
        f"- [API de productos]({SITE_URL}/api/docs/): Documentación técnica de la API REST",
    ])
    
    return HttpResponse("\n".join(lines), content_type="text/markdown; charset=utf-8")

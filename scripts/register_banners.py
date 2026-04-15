import os
import django
from django.conf import settings

# Setup Django environment
if not settings.configured:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_bulonera.settings.local')
    django.setup()

from store.models import CarouselImage

# Desactivar carruseles anteriores para un debut limpio
CarouselImage.objects.all().update(is_active=False)

banners = [
    {
        'image': 'photos/carousel/banner_buloneria_no_logo.png',
        'title': 'Bulonería Industrial',
        'description': 'Materia prima de alta calidad para tus proyectos.',
        'position': 1
    },
    {
        'image': 'photos/carousel/banner_herramientas_no_logo.png',
        'title': 'Herramientas Profesionales',
        'description': 'Precisión y robustez en cada trabajo.',
        'position': 2
    },
    {
        'image': 'photos/carousel/banner_envios_no_logo.png',
        'title': 'Envíos a Todo el País',
        'description': 'Recibí lo que necesitás, estés donde estés.',
        'position': 3
    }
]

for b in banners:
    obj, created = CarouselImage.objects.update_or_create(
        image=b['image'],
        defaults={
            'title': b['title'],
            'description': b['description'],
            'position': b['position'],
            'is_active': True
        }
    )
    status = "Creado" if created else "Actualizado"
    print(f"{status}: {b['title']}")

print("Fase 5 completada: Banners premium registrados con éxito.")

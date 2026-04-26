import django
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_bulonera.settings.local')
django.setup()

from django.core.cache import cache
from store.services import GoogleReviewsService

# Borrar cache vieja
cache.delete('google_places_reviews_data')
print("Cache borrada.")

# Obtener datos frescos
data = GoogleReviewsService.get_cached_reviews()
print(f"Rating: {data.get('rating')}")
print(f"Total: {data.get('total')}")
print(f"Reviews: {len(data.get('reviews', []))}")
print(f"Is fallback: {data.get('is_fallback')}")
for r in data.get('reviews', []):
    print(f"  - {r['author_name']} ({r['rating']}★): {r['text'][:50]}...")

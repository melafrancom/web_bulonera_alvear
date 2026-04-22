#!/usr/bin/env python
"""Verificar que los slugs fueron actualizados correctamente"""
import os
import sys
import django

# Asegurar que el directorio raíz del proyecto (/app) esté en sys.path
# para que Python pueda encontrar el módulo 'web_bulonera'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Prioridad: argumento CLI → variable de entorno → production por defecto
settings = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('DJANGO_SETTINGS_MODULE', 'web_bulonera.settings.production')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings)
django.setup()

from store.models import Product

# Contar productos con slugs placeholder
placeholder_count = Product.objects.filter(slug__startswith='producto-').count()
total_products = Product.objects.count()
updated_count = total_products - placeholder_count

print(f"\n{'='*70}")
print(f"📊 VERIFICACIÓN DE ACTUALIZACIÓN DE SLUGS")
print(f"{'='*70}")
print(f"Total de productos:              {total_products:,}")
print(f"Aún con slug placeholder:        {placeholder_count}")
print(f"Actualizados a slug real:        {updated_count:,}")
print(f"Porcentaje actualizado:          {(updated_count/total_products)*100:.1f}%")
print(f"{'='*70}\n")

if placeholder_count == 0:
    print("✅ ¡ÉXITO! Todos los slugs fueron actualizados correctamente\n")
else:
    print(f"⚠️  Aún hay {placeholder_count} productos con slugs placeholder\n")
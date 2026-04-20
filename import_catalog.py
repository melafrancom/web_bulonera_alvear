"""
Script de importación de catálogo completo.

Ejecutar via:
  docker-compose exec bulonera_web python manage.py shell < import_catalog.py

Este script:
1. Lee el archivo Excel completo vía ProductService._parse_file()
2. Importa todos los productos usando import_from_file(dry_run=False)
3. Reporta estadísticas finales
"""

import os
import sys
from pathlib import Path

EXCEL_PATH = '/app/2 lista completa para web.xlsx'

print(f'\n{"="*80}')
print('📥 IMPORTACIÓN DE CATÁLOGO COMPLETO')
print(f'{"="*80}\n')

print(f'📂 Archivo: {EXCEL_PATH}')

if not os.path.exists(EXCEL_PATH):
    print(f'❌ ERROR: Archivo no encontrado')
    sys.exit(1)

print(f'✓ Archivo accesible\n')

# Importar servicios
from store.services import ProductService
from store.models import Product

try:
    # Verificar DB vacía
    existing_count = Product.objects.count()
    if existing_count > 0:
        print(f'⚠️  ADVERTENCIA: La DB ya contiene {existing_count} productos')
        print(f'   Se recomienda haber ejecutado "python manage.py clear_products" primero')
        response = input('¿Deseas continuar de todas formas? (s/N): ').strip().upper()
        if response != 'S':
            print('❌ Importación cancelada')
            sys.exit(1)
    
    print('⏳ Iniciando importación...')
    print(f'{"="*80}\n')
    
    # Importar productos
    result = ProductService.import_from_file(
        EXCEL_PATH,
        dry_run=False,
        update_prices=False
    )
    
    # Mostrar resultados
    print(f'\n{"="*80}')
    print('✅ IMPORTACIÓN COMPLETADA')
    print(f'{"="*80}')
    
    print(f'\n📊 ESTADÍSTICAS:')
    print(f'   Productos creados:  {result.created}')
    print(f'   Productos actualizados: {result.updated}')
    print(f'   Errores: {result.errors}')
    
    if result.error_details:
        print(f'\n⚠️  ERRORES DETECTADOS (mostrando primeros 10):')
        for idx, error in result.error_details[:10]:
            print(f'      Fila {idx}: {error}')
        if len(result.error_details) > 10:
            print(f'      ... y {len(result.error_details) - 10} más')
    
    # Validación final
    final_count = Product.objects.count()
    corrupted_count = Product.objects.filter(code__endswith='.0').count()
    
    print(f'\n🔍 VALIDACIÓN POST-IMPORTACIÓN:')
    print(f'   Total en DB: {final_count}')
    print(f'   Productos con .0: {corrupted_count}')
    
    if corrupted_count > 0:
        print(f'\n❌ ERROR: Se detectaron {corrupted_count} productos corruptos con .0')
        sys.exit(1)
    
    if final_count < 13000:
        print(f'\n⚠️  ADVERTENCIA: Solo {final_count} productos, se esperaban ~13985')
        print(f'   Verifica si hay errores en el Excel o restricciones de BD')
    else:
        print(f'\n✅ OK: Catálogo importado correctamente')
    
    print(f'\n{"="*80}')
    print(f'Importación finalizada. Puedes proceder a FASE 3 (Auditoría Post-Mortem)')
    print(f'{"="*80}\n')
    
    sys.exit(0)

except Exception as e:
    print(f'\n❌ ERROR durante importación:')
    print(f'   {type(e).__name__}: {str(e)}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

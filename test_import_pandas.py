"""
Script de validación rápida: Verificar que _parse_file() elimina .0 de códigos.

Ejecutar via:
  docker-compose exec bulonera_web python manage.py shell < test_import_pandas.py

Este script:
1. Lee las primeras líneas (o todas) del Excel
2. Valida que los códigos NO contengan .0 después del parseo
3. Reporte de hallazgos
"""

import os
import sys
from pathlib import Path

# Ruta del Excel a validar (cambiar según necesidad)
EXCEL_PATH = '/app/2 lista completa para web.xlsx'

# Fallback: buscar en directorio actual si no existe en /app
if not os.path.exists(EXCEL_PATH):
    EXCEL_PATH = '/app/Arandelas.xlsx'
    if not os.path.exists(EXCEL_PATH):
        EXCEL_PATH = './2 lista completa para web.xlsx'

print(f'\n{"="*70}')
print('🔍 VALIDACIÓN RÁPIDA: Test de _parse_file() y eliminación de .0')
print(f'{"="*70}\n')

print(f'📂 Buscando archivo: {EXCEL_PATH}')

if not os.path.exists(EXCEL_PATH):
    print(f'❌ ERROR: Archivo no encontrado en {EXCEL_PATH}')
    print(f'   Intenta cambiar EXCEL_PATH en este script.')
    sys.exit(1)

print(f'✓ Archivo encontrado\n')

# Importar servicios
from store.services import ProductService

try:
    print('⏳ Leyendo Excel vía _parse_file()...')
    data = ProductService._parse_file(EXCEL_PATH)
    
    if not data:
        print('❌ ERROR: Excel vacío o no tiene datos')
        sys.exit(1)
    
    total_rows = len(data)
    print(f'✓ Leído exitosamente: {total_rows} filas\n')
    
    # Análisis de códigos
    print('📊 ANÁLISIS DE CÓDIGOS:')
    print(f'{"="*70}')
    
    codes_with_decimal = []
    codes_with_leading_zeros = []
    sample_codes = []
    invalid_codes = []
    
    for idx, row in enumerate(data):
        code = row.get('code')
        
        if code is None or str(code).strip() == '' or str(code).strip() in ['None', 'nan', 'NaN']:
            invalid_codes.append((idx, 'vacío'))
            continue
        
        code_str = str(code).strip()
        
        # Detectar .0
        if code_str.endswith('.0'):
            codes_with_decimal.append((idx, code_str))
        
        # Detectar ceros a la izquierda
        if code_str.startswith('0') and len(code_str) > 1:
            codes_with_leading_zeros.append(code_str)
        
        # Sample de primeros códigos
        if idx < 5:
            sample_codes.append(code_str)
    
    # Reportes
    print(f'\n🔢 Primeros 5 códigos leídos:')
    for code in sample_codes:
        print(f'   • {repr(code)} (tipo: {type(code).__name__}, len: {len(code)})')
    
    print(f'\n⚠️  Códigos con .0 (PROBLEMAS):')
    if codes_with_decimal:
        print(f'   ❌ CRÍTICO: {len(codes_with_decimal)} códigos aún tienen .0')
        for idx, code in codes_with_decimal[:10]:
            print(f'      Fila {idx}: {repr(code)}')
        if len(codes_with_decimal) > 10:
            print(f'      ... y {len(codes_with_decimal) - 10} más')
    else:
        print(f'   ✅ OK: Ningún código contiene .0')
    
    print(f'\n✨ Códigos con ceros a la izquierda (ESPERADO):')
    if codes_with_leading_zeros:
        print(f'   ✓ {len(set(codes_with_leading_zeros))} códigos únicos con ceros a la izquierda')
        for code in list(set(codes_with_leading_zeros))[:5]:
            print(f'      • {repr(code)}')
        if len(set(codes_with_leading_zeros)) > 5:
            print(f'      ... y {len(set(codes_with_leading_zeros)) - 5} más')
    else:
        print(f'   ⚠️  No hay códigos con ceros a la izquierda (podría ser normal)')
    
    print(f'\n❌ Códigos vacíos/inválidos:')
    if invalid_codes:
        print(f'   {len(invalid_codes)} códigos vacíos')
    else:
        print(f'   ✓ OK: Todos los códigos están presentes')
    
    # Decisión final
    print(f'\n{"="*70}')
    print('🎯 DECISIÓN FINAL:')
    print(f'{"="*70}')
    
    if codes_with_decimal:
        print(f'\n❌ BLOQUEADO: El fix de _parse_file() NO está funcionando.')
        print(f'   {len(codes_with_decimal)} códigos aún tienen .0')
        print(f'\n   Acción recomendada:')
        print(f'   1. Revisar store/services.py línea 349 (str.replace)')
        print(f'   2. Verificar que .0 aparece en el Excel original')
        print(f'   3. Ejecutar de nuevo este test después del fix')
        sys.exit(1)
    else:
        print(f'\n✅ APROBADO: El fix está funcionando correctamente.')
        print(f'   • {total_rows} filas procesadas')
        print(f'   • 0 códigos con .0')
        print(f'   • Códigos con ceros a la izquierda preservados')
        print(f'\n   Puedes proceder con FASE 2 (Purga y Re-importación).')
        print(f'{"="*70}\n')
        sys.exit(0)

except Exception as e:
    print(f'\n❌ ERROR durante validación:')
    print(f'   {type(e).__name__}: {str(e)}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

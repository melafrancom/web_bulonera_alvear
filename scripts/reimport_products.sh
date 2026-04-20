#!/bin/bash
# Script de Reimportación de Productos
# Proyecto: Bulonera Alvear
# Fecha: 2026-04-20

set -e  # Salir si hay error

echo "=========================================="
echo "  REIMPORTACIÓN DE PRODUCTOS"
echo "  Bulonera Alvear - Fix Bug Importación"
echo "=========================================="
echo ""

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar que estamos en el directorio correcto
if [ ! -f "docker-compose.yml" ]; then
    echo -e "${RED}Error: Este script debe ejecutarse desde el directorio raíz del proyecto${NC}"
    exit 1
fi

# Paso 1: Verificar estado actual
echo -e "${YELLOW}[1/5] Verificando estado actual del catálogo...${NC}"
docker-compose exec -T bulonera_web python manage.py shell << EOF
from store.models import Product
total = Product.objects.count()
corruptos = Product.objects.filter(code__endswith='.0').count()
print(f'Total productos: {total}')
print(f'Productos con .0: {corruptos}')
EOF

echo ""
read -p "¿Desea continuar con la reimportación? (s/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo -e "${RED}Operación cancelada${NC}"
    exit 0
fi

# Paso 2: Backup de la base de datos
echo ""
echo -e "${YELLOW}[2/5] Creando backup de la base de datos...${NC}"
BACKUP_FILE="backup_pre_reimport_$(date +%Y%m%d_%H%M%S).sql"
docker-compose exec -T db_mariadb mysqldump -u root -p${MYSQL_ROOT_PASSWORD:-root} bulonera_web > "$BACKUP_FILE"
echo -e "${GREEN}✓ Backup creado: $BACKUP_FILE${NC}"

# Paso 3: Eliminar productos corruptos
echo ""
echo -e "${YELLOW}[3/5] Eliminando productos con sufijo .0...${NC}"
docker-compose exec -T bulonera_web python manage.py shell << EOF
from store.models import Product
corruptos = Product.objects.filter(code__endswith='.0')
count = corruptos.count()
corruptos.delete()
print(f'✓ Eliminados {count} productos corruptos')
EOF

# Paso 4: Instrucciones para reimportación manual
echo ""
echo -e "${YELLOW}[4/5] Reimportación de productos${NC}"
echo ""
echo "Por favor, siga estos pasos para reimportar los productos:"
echo ""
echo "1. Abra el panel Admin en su navegador:"
echo "   http://localhost:8002/admin/store/product/import-products/"
echo ""
echo "2. Seleccione el archivo Excel a importar:"
echo "   - Arandelas.xlsx (para arandelas)"
echo "   - 2 lista completa para web.xlsx (para catálogo completo)"
echo ""
echo "3. Haga clic en 'Importar'"
echo ""
echo "4. Verifique que no haya errores en el resultado"
echo ""
read -p "Presione ENTER cuando haya completado la importación..." -r

# Paso 5: Verificar resultado
echo ""
echo -e "${YELLOW}[5/5] Verificando resultado de la reimportación...${NC}"
docker-compose exec -T bulonera_web python manage.py shell << EOF
from store.models import Product
total = Product.objects.count()
corruptos = Product.objects.filter(code__endswith='.0').count()
print('')
print('========================================')
print('  RESULTADO DE LA REIMPORTACIÓN')
print('========================================')
print(f'Total productos: {total}')
print(f'Productos con .0: {corruptos}')
print('')
if corruptos == 0:
    print('✓ ¡ÉXITO! No hay productos corruptos')
else:
    print(f'⚠ ADVERTENCIA: Aún hay {corruptos} productos con .0')
    print('  Verifique que la importación se haya realizado correctamente')
print('========================================')
EOF

echo ""
echo -e "${GREEN}=========================================="
echo "  PROCESO COMPLETADO"
echo "==========================================${NC}"
echo ""
echo "Backup guardado en: $BACKUP_FILE"
echo ""
echo "Si algo salió mal, puede restaurar el backup con:"
echo "docker-compose exec -T db_mariadb mysql -u root -p${MYSQL_ROOT_PASSWORD:-root} bulonera_web < $BACKUP_FILE"

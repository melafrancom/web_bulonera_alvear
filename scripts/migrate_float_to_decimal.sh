#!/bin/bash
# ============================================
# Migración FloatField → DecimalField
# ============================================
# Script para migrar Product.price y Product.sale_price
# de FloatField a DecimalField
# 
# IMPORTANTE: Crear backup antes de ejecutar
# ============================================

set -e

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}"
echo "╔════════════════════════════════════════╗"
echo "║   ⚠️  MIGRACIÓN FLOAT → DECIMAL       ║"
echo "╚════════════════════════════════════════╝"
echo -e "${NC}"

echo "Esta operación modificará los campos de precio en la base de datos"
echo "de FloatField a DecimalField para mayor precisión."
echo ""

# Verificar que existe backup reciente
BACKUP_DIR="/var/www/bulonera/backups"
LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/backup_buloneraalvearDB_*.sql.gz 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo -e "${RED}❌ No se encontró ningún backup reciente${NC}"
    echo ""
    read -p "¿Crear backup ahora? (s/n): " CREATE_BACKUP
    if [ "$CREATE_BACKUP" = "s" ]; then
        bash scripts/backup_database.sh
    else
        echo -e "${RED}❌ Operación cancelada - Se requiere backup${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Backup encontrado: $(basename $LATEST_BACKUP)${NC}"
    BACKUP_DATE=$(stat -c %y "$LATEST_BACKUP" | cut -d' ' -f1)
    echo "   Fecha: $BACKUP_DATE"
fi

echo ""
echo -e "${YELLOW}⚠️  ADVERTENCIA: Esta operación es irreversible${NC}"
read -p "¿Continuar con la migración? (escribir 'SI' para confirmar): " CONFIRM

if [ "$CONFIRM" != "SI" ]; then
    echo "❌ Operación cancelada"
    exit 0
fi

echo ""
echo "🔄 Iniciando migración..."
echo ""

# Paso 1: Verificar modelo actual
echo "📋 Paso 1/4: Verificando modelo actual..."
docker-compose -f docker-compose.production.yml run --rm bulonera_web python manage.py shell <<EOF
from store.models import Product
import inspect
price_field = Product._meta.get_field('price')
sale_price_field = Product._meta.get_field('sale_price')
print(f"price: {price_field.__class__.__name__}")
print(f"sale_price: {sale_price_field.__class__.__name__}")
EOF
echo ""

# Paso 2: Crear migración
echo "📝 Paso 2/4: Creando migración..."
docker-compose -f docker-compose.production.yml run --rm bulonera_web python manage.py makemigrations store
echo ""

# Paso 3: Aplicar migración
echo "🔄 Paso 3/4: Aplicando migración..."
docker-compose -f docker-compose.production.yml run --rm bulonera_web python manage.py migrate store
echo ""

# Paso 4: Verificar cambios
echo "✅ Paso 4/4: Verificando cambios..."
docker-compose -f docker-compose.production.yml run --rm bulonera_web python manage.py shell <<EOF
from store.models import Product
from decimal import Decimal

# Verificar tipo de campo
price_field = Product._meta.get_field('price')
sale_price_field = Product._meta.get_field('sale_price')
print(f"✅ price: {price_field.__class__.__name__}")
print(f"✅ sale_price: {sale_price_field.__class__.__name__}")

# Verificar un producto de ejemplo
product = Product.objects.first()
if product:
    print(f"\n📦 Producto de ejemplo: {product.product_name}")
    print(f"   Precio: {product.price} (tipo: {type(product.price).__name__})")
    if product.sale_price:
        print(f"   Precio oferta: {product.sale_price} (tipo: {type(product.sale_price).__name__})")
EOF
echo ""

echo -e "${GREEN}"
echo "╔════════════════════════════════════════╗"
echo "║   ✅ MIGRACIÓN COMPLETADA              ║"
echo "╚════════════════════════════════════════╝"
echo -e "${NC}"

echo "📊 Resumen:"
echo "   - FloatField → DecimalField(max_digits=10, decimal_places=2)"
echo "   - Backup disponible en: $LATEST_BACKUP"
echo ""

echo "🧪 Verificación recomendada:"
echo "   1. Verificar precios en admin: https://buloneraalvear.online/admin/store/product/"
echo "   2. Verificar catálogo: https://buloneraalvear.online/store/"
echo "   3. Verificar API: https://buloneraalvear.online/api/v1/store/products/"
echo ""

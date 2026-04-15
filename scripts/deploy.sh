#!/bin/bash
# ============================================
# Deploy Script - Bulonera Web
# ============================================
# Script automatizado para deploy en VPS
# Ejecutar desde: /var/www/bulonera/web
# ============================================

set -e

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuración
PROJECT_DIR="/var/www/bulonera/web"
COMPOSE_FILE="docker compose.production.yml"

echo -e "${BLUE}"
echo "╔════════════════════════════════════════╗"
echo "║   🚀 BULONERA WEB - DEPLOY SCRIPT     ║"
echo "╚════════════════════════════════════════╝"
echo -e "${NC}"

# Verificar que estamos en el directorio correcto
if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}❌ Error: No se encontró $COMPOSE_FILE${NC}"
    echo "   Ejecutar desde: $PROJECT_DIR"
    exit 1
fi

# Paso 1: Git Pull
echo -e "${YELLOW}📥 Paso 1/8: Actualizando código desde Git...${NC}"
git pull origin master
echo -e "${GREEN}✅ Código actualizado${NC}"
echo ""

# Paso 2: Backup de BD
echo -e "${YELLOW}💾 Paso 2/8: Creando backup de base de datos...${NC}"
read -p "¿Crear backup de BD? (s/n): " CREATE_BACKUP
if [ "$CREATE_BACKUP" = "s" ]; then
    bash scripts/backup_database.sh
else
    echo "⏭️  Backup omitido"
fi
echo ""

# Paso 3: Build
echo -e "${YELLOW}🔨 Paso 3/8: Building Docker image...${NC}"
docker compose -f "$COMPOSE_FILE" build --no-cache
echo -e "${GREEN}✅ Build completado${NC}"
echo ""

# Paso 4: Verificar conexión a BD
echo -e "${YELLOW}🔍 Paso 4/8: Verificando conexión a base de datos...${NC}"
docker compose -f "$COMPOSE_FILE" run --rm bulonera_web python manage.py check --database default
echo -e "${GREEN}✅ Conexión a BD verificada${NC}"
echo ""

# Paso 5: Migraciones
echo -e "${YELLOW}🔄 Paso 5/8: Aplicando migraciones...${NC}"
docker compose -f "$COMPOSE_FILE" run --rm bulonera_web python manage.py migrate --no-input
echo -e "${GREEN}✅ Migraciones aplicadas${NC}"
echo ""

# Paso 6: Collectstatic
echo -e "${YELLOW}📦 Paso 6/8: Recolectando archivos estáticos...${NC}"
docker compose -f "$COMPOSE_FILE" run --rm bulonera_web python manage.py collectstatic --no-input
echo -e "${GREEN}✅ Static files recolectados${NC}"
echo ""

# Paso 7: Restart containers
echo -e "${YELLOW}🔄 Paso 7/8: Reiniciando contenedores...${NC}"
docker compose -f "$COMPOSE_FILE" down
docker compose -f "$COMPOSE_FILE" up -d
echo -e "${GREEN}✅ Contenedores reiniciados${NC}"
echo ""

# Paso 8: Health Check
echo -e "${YELLOW}🏥 Paso 8/8: Verificando servicios...${NC}"
sleep 5  # Esperar a que los servicios inicien
docker compose -f "$COMPOSE_FILE" ps
echo ""

# Test local
echo "🧪 Test local..."
if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8002/ | grep -q "200"; then
    echo -e "${GREEN}✅ Django respondiendo correctamente${NC}"
else
    echo -e "${RED}❌ Django no responde${NC}"
    echo "   Verificar logs: docker compose -f $COMPOSE_FILE logs --tail=50"
    exit 1
fi
echo ""

# Logs recientes
echo -e "${YELLOW}📝 Logs recientes:${NC}"
docker compose -f "$COMPOSE_FILE" logs --tail=20
echo ""

echo -e "${GREEN}"
echo "╔════════════════════════════════════════╗"
echo "║   ✅ DEPLOY COMPLETADO EXITOSAMENTE   ║"
echo "╚════════════════════════════════════════╝"
echo -e "${NC}"

echo "🔗 URLs:"
echo "   - Web: https://buloneraalvear.online/"
echo "   - API: https://buloneraalvear.online/api/v1/"
echo "   - Docs: https://buloneraalvear.online/api/docs/"
echo ""

echo "📊 Comandos útiles:"
echo "   - Ver logs: docker compose -f $COMPOSE_FILE logs -f"
echo "   - Health check: bash scripts/health_check.sh"
echo "   - Restart: docker compose -f $COMPOSE_FILE restart"
echo ""

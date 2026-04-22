#!/bin/bash
# ============================================
# Health Check - Verificación de Servicios
# ============================================
# Script para verificar el estado de todos los
# servicios en producción
# ============================================

set -e

echo "🏥 Health Check - Bulonera Web"
echo "=============================="
echo ""

# Colores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Función para verificar servicio
check_service() {
    local name=$1
    local command=$2
    
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ $name${NC}"
        return 0
    else
        echo -e "${RED}❌ $name${NC}"
        return 1
    fi
}

# Función para verificar URL
check_url() {
    local name=$1
    local url=$2
    local expected_code=${3:-200}
    
    local response=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    
    if [ "$response" = "$expected_code" ]; then
        echo -e "${GREEN}✅ $name ($response)${NC}"
        return 0
    else
        echo -e "${RED}❌ $name (esperado: $expected_code, obtenido: $response)${NC}"
        return 1
    fi
}

# Contador de errores
ERRORS=0

echo "🐳 Docker Services"
echo "------------------"
if docker compose -f /var/www/bulonera/web_bulonera_alvear/docker-compose.production.yml ps | grep -q "Up"; then
    echo -e "${GREEN}✅ Docker Compose${NC}"
    docker compose -f /var/www/bulonera/web_bulonera_alvear/docker-compose.production.yml ps
else
    echo -e "${RED}❌ Docker Compose${NC}"
    ((ERRORS++))
fi
echo ""

echo "🗄️  Database"
echo "------------"
check_service "MariaDB" "mysql -u bulonera_user -pDB_PASSWORD -e 'SELECT 1' buloneraalvearDB" || ((ERRORS++))
echo ""

echo "🔴 Redis"
echo "--------"
check_service "Redis Ping" "redis-cli ping" || ((ERRORS++))
check_service "Redis DB 3 (Celery Broker)" "redis-cli -n 3 ping" || ((ERRORS++))
check_service "Redis DB 4 (Celery Result)" "redis-cli -n 4 ping" || ((ERRORS++))
check_service "Redis DB 5 (Cache)" "redis-cli -n 5 ping" || ((ERRORS++))
echo ""

echo "🌐 Web Services"
echo "---------------"
check_url "Django Local" "http://127.0.0.1:8003/" || ((ERRORS++))
check_url "HTTPS Public" "https://buloneraalvear.online/" || ((ERRORS++))
check_url "API Products" "https://buloneraalvear.online/api/v1/store/products/" || ((ERRORS++))
check_url "API Docs" "https://buloneraalvear.online/api/docs/" || ((ERRORS++))
check_url "Static Files" "https://buloneraalvear.online/static/css/style.css" || ((ERRORS++))
echo ""

echo "🔒 SSL Certificate"
echo "------------------"
if openssl s_client -connect buloneraalvear.online:443 -servername buloneraalvear.online </dev/null 2>/dev/null | grep -q "Verify return code: 0"; then
    echo -e "${GREEN}✅ SSL Certificate Valid${NC}"
    # Mostrar fecha de expiración
    EXPIRY=$(echo | openssl s_client -connect buloneraalvear.online:443 -servername buloneraalvear.online 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2)
    echo "   Expira: $EXPIRY"
else
    echo -e "${RED}❌ SSL Certificate Invalid${NC}"
    ((ERRORS++))
fi
echo ""

echo "🌐 OpenLiteSpeed"
echo "----------------"
check_service "OLS Running" "systemctl is-active lsws" || ((ERRORS++))
echo ""

echo "📊 Disk Space"
echo "-------------"
df -h /var/www/bulonera | tail -n 1 | awk '{
    used=$5+0;
    if (used >= 90) {
        printf "\033[0;31m❌ Disk Usage: %s (Critical)\033[0m\n", $5
    } else if (used >= 80) {
        printf "\033[1;33m⚠️  Disk Usage: %s (Warning)\033[0m\n", $5
    } else {
        printf "\033[0;32m✅ Disk Usage: %s\033[0m\n", $5
    }
}'
echo ""

echo "📝 Recent Logs"
echo "--------------"
if [ -f /var/www/bulonera/logs/django.log ]; then
    echo "Últimas 5 líneas de django.log:"
    tail -n 5 /var/www/bulonera/logs/django.log
else
    echo -e "${YELLOW}⚠️  No se encontró django.log${NC}"
fi
echo ""

echo "=============================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}🎉 Todos los servicios funcionando correctamente${NC}"
    exit 0
else
    echo -e "${RED}⚠️  Se encontraron $ERRORS errores${NC}"
    exit 1
fi

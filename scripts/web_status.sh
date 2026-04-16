#!/bin/bash
# ====================================================
# web_status.sh - Estado del sistema Bulonera Web
# ====================================================
# Instalar en el VPS:
#   sudo cp /var/www/bulonera/web_bulonera_alvear/scripts/web_status.sh /usr/local/bin/web_status.sh
#   sudo chmod +x /usr/local/bin/web_status.sh
# Ejecutar con: sudo web_status.sh
# ====================================================

WEB_DIR="/var/www/bulonera/web_bulonera_alvear"
COMPOSE_FILE="docker-compose.production.yml"
WEB_PORT="8003"
WEB_CONTAINER="bulonera_web_production"
REDIS_CONTAINER="bulonera_web_redis"
CELERY_WORKER_CONTAINER="bulonera_web_celery_worker_production"
CELERY_BEAT_CONTAINER="bulonera_web_celery_beat_production"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}  Bulonera Web - Estado del Sistema ${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ====================================================
# 1. Contenedores Docker
# ====================================================
echo -e "${CYAN}🐳 Contenedores Docker:${NC}"
echo ""
docker compose -f "$WEB_DIR/$COMPOSE_FILE" ps
echo ""

# ====================================================
# 2. Respuesta HTTP
# ====================================================
echo -e "${CYAN}🌐 Respuesta HTTP:${NC}"
echo ""
HTTP_INFO=$(curl -s -o /dev/null -w "%{http_code} (%{time_total}s)" "http://127.0.0.1:${WEB_PORT}/")
HTTP_CODE=$(echo "$HTTP_INFO" | awk '{print $1}')
if [[ "$HTTP_CODE" =~ ^[23] ]]; then
    echo -e "  Web: ${GREEN}${HTTP_INFO}${NC}"
else
    echo -e "  Web: ${RED}${HTTP_INFO} — NO RESPONDE${NC}"
fi
echo ""

# ====================================================
# 3. Estado de contenedores clave
# ====================================================
echo -e "${CYAN}📋 Estado de Servicios:${NC}"
echo ""

check_container() {
    local NAME=$1
    local LABEL=$2
    local STATUS
    STATUS=$(docker inspect -f '{{.State.Status}}' "$NAME" 2>/dev/null || echo "missing")
    if [ "$STATUS" == "running" ]; then
        echo -e "  $LABEL: ${GREEN}✓ Activo${NC}"
    else
        echo -e "  $LABEL: ${RED}✗ $STATUS${NC}"
    fi
}

check_container "$WEB_CONTAINER"          "Django (uWSGI)"
check_container "$REDIS_CONTAINER"        "Redis"
check_container "$CELERY_WORKER_CONTAINER" "Celery Worker"
check_container "$CELERY_BEAT_CONTAINER"  "Celery Beat"
echo ""

# ====================================================
# 4. Recursos del sistema
# ====================================================
echo -e "${CYAN}💾 Espacio en disco:${NC}"
df -h / | awk 'NR==2 {print "  Usado: "$3" / "$2" ("$5")"}'
echo ""

echo -e "${CYAN}🧠 RAM:${NC}"
free -h | awk 'NR==2 {print "  Usado: "$3" / "$2}'
echo ""

# ====================================================
# 5. Logs recientes de Django
# ====================================================
echo -e "${CYAN}📝 Logs recientes (últimas 10 líneas):${NC}"
echo ""
LOGFILE="/var/www/bulonera/logs/django.log"
if [ -f "$LOGFILE" ]; then
    tail -10 "$LOGFILE"
else
    echo "  (log no encontrado en $LOGFILE)"
fi
echo ""

# ====================================================
# 6. Conexiones MariaDB
# ====================================================
echo -e "${CYAN}📊 Conexiones de Base de Datos:${NC}"
echo ""
DB_CONNS=$(sudo mysql -e "SHOW STATUS LIKE 'Threads_connected';" 2>/dev/null | awk 'NR==2 {print $2}')
if [ -n "$DB_CONNS" ]; then
    echo -e "  Conexiones activas: ${GREEN}${DB_CONNS}${NC}"
else
    echo -e "  ${RED}MySQL no disponible o sin permisos${NC}"
fi
echo ""

echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

#!/bin/bash
# ====================================================
# deploy_web.sh - Actualizar Bulonera Web en producción
# ====================================================
# Ejecutar desde cualquier lugar como:
#   sudo /var/www/bulonera/web_bulonera_alvear/scripts/deploy.sh
# ====================================================

set -euo pipefail

# ====================================================
# Configuración
# ====================================================
WEB_DIR="/var/www/bulonera/web_bulonera_alvear"
COMPOSE_FILE="docker-compose.production.yml"
DJANGO_SETTINGS="web_bulonera.settings.production"

# Puertos y contenedores
WEB_PORT="8003"
WEB_CONTAINER="bulonera_web"
REDIS_CONTAINER="redis"
CELERY_WORKER_CONTAINER="bulonera_web_celery_worker"
CELERY_BEAT_CONTAINER="bulonera_web_celery_beat"

# Colores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ====================================================
# Funciones auxiliares
# ====================================================
exec_web() {
    docker compose -f "$COMPOSE_FILE" exec -T "$WEB_CONTAINER" "$@"
}
step() { echo -e "\n${YELLOW}━━━ $1 ━━━${NC}"; }
ok()   { echo -e "${GREEN}✓ $1${NC}"; }
fail() { echo -e "${RED}✗ $1${NC}"; }

# ====================================================
# Inicio
# ====================================================
echo -e "${CYAN}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   🚀  Bulonera Web — Deploy a Producción"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${NC}"

# Moverse al directorio del proyecto
cd "$WEB_DIR"

# Verificar que el compose file existe
if [ ! -f "$COMPOSE_FILE" ]; then
    fail "No se encontró $COMPOSE_FILE en $WEB_DIR"
    exit 1
fi

# ====================================================
# 1. Git Pull
# ====================================================
step "1/8 Actualizando código..."
git fetch origin main
git reset --hard origin/main
ok "Código actualizado"

# ====================================================
# 2. Build de imagen
# ====================================================
step "2/8 Construyendo imagen Docker..."
docker compose -f "$COMPOSE_FILE" build
ok "Imagen construida"

# ====================================================
# 3. Migraciones (contenedor temporal, sin afectar al live)
# ====================================================
step "3/8 Ejecutando migraciones..."
docker compose -f "$COMPOSE_FILE" run --rm \
    -e DJANGO_SETTINGS_MODULE="$DJANGO_SETTINGS" \
    bulonera_web python manage.py migrate --no-input
ok "Migraciones aplicadas"

# ====================================================
# 4. Collectstatic
# ====================================================
step "4/8 Recolectando archivos estáticos..."
docker compose -f "$COMPOSE_FILE" run --rm \
    -e DJANGO_SETTINGS_MODULE="$DJANGO_SETTINGS" \
    bulonera_web python manage.py collectstatic --no-input
ok "Archivos estáticos recolectados"

# ====================================================
# 5. Levantar/actualizar servicios
#    "up -d" solo recrea los contenedores que cambiaron.
#    Redis NO se reinicia si no cambió → cero downtime.
# ====================================================
step "5/8 Reiniciando servicios..."
docker compose -f "$COMPOSE_FILE" up -d

# Reiniciar workers explícitamente para garantizar que recargan el nuevo código Python
echo "⚙️  Recargando Celery Workers..."
docker compose -f "$COMPOSE_FILE" restart "$CELERY_WORKER_CONTAINER" "$CELERY_BEAT_CONTAINER"

ok "Servicios levantados"

# ====================================================
# 5.5 Optimización SEO de Slugs
# ====================================================
step "5.5 Verificando estado de Slugs SEO..."

# Ejecutar el script de verificación para ver el estado real de la BD
exec_web python scripts/verify_slugs.py

# Consultar al usuario si desea ejecutar la optimización interactiva
echo ""
read -p "¿Deseas ejecutar la regeneración de slugs SEO en PRODUCCIÓN ahora? (s/n): " -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    echo "📋 Validando cambios (dry-run)..."
    exec_web python manage.py seo_optimize_slugs --dry-run
    
    echo ""
    read -p "¿Confirmas aplicar estos cambios de slugs en PRODUCCIÓN? (s/n): " -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        echo "⚙️  Aplicando regeneración de slugs..."
        exec_web python manage.py seo_optimize_slugs
        ok "Slugs regenerados"
        
        echo "📊 Verificando resultados finales..."
        exec_web python scripts/verify_slugs.py
    else
        echo "⏭️  Regeneración de slugs cancelada"
    fi
else
    echo "⏭️  Regeneración de slugs omitida"
fi

# ====================================================
# 6. Verificación de arranque
# ====================================================
step "7/8 Verificando arranque (espera hasta 30s)..."

for i in $(seq 1 6); do
    sleep 5
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${WEB_PORT}/" || echo "000")
    if [[ "$HTTP_CODE" =~ ^[23] ]]; then
        ok "Django respondiendo (HTTP $HTTP_CODE)"
        break
    fi
    echo "   Intento $i/6 → HTTP $HTTP_CODE, esperando..."
    if [ "$i" -eq 6 ]; then
        fail "Django no responde después de 30s"
        echo ""
        echo "📋 Logs recientes:"
        docker compose -f "$COMPOSE_FILE" logs --tail=30
        exit 1
    fi
done

# ====================================================
# 8. Estado final
# ====================================================
step "8/8 Estado final del sistema"
docker compose -f "$COMPOSE_FILE" ps

# Verificar Redis y Celery (usando docker compose ps o inspect al contenedor real)
# Buscamos por nombre real de contenedor
if [ "$(docker inspect -f '{{.State.Status}}' bulonera_web_redis 2>/dev/null)" == "running" ]; then
    ok "Redis: Activo"
else
    fail "Redis: Inactivo"
fi

if [ "$(docker inspect -f '{{.State.Status}}' bulonera_web_celery_worker_production 2>/dev/null)" == "running" ]; then
    ok "Celery Worker: Activo"
else
    fail "Celery Worker: Inactivo"
fi

# ====================================================
# Resumen final
# ====================================================
echo ""
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✓ Deploy completado exitosamente${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "🔗 URLs:"
echo "   - Web:  https://buloneraalvear.online/"
echo "   - API:  https://buloneraalvear.online/api/v1/"
echo "   - Docs: https://buloneraalvear.online/api/docs/"
echo ""
echo "📊 Comandos útiles:"
echo "   - Ver logs:     docker compose -f $WEB_DIR/$COMPOSE_FILE logs -f"
echo "   - Estado:       sudo web_status.sh"
echo ""

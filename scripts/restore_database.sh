#!/bin/bash
# ============================================
# Restaurar Base de Datos MariaDB
# ============================================
# Script para restaurar backups en caso de emergencia
# ============================================

set -e

# Configuración
BACKUP_DIR="/var/www/bulonera/backups"
DB_NAME="buloneraalvearDB"
DB_USER="bulonera_user"

echo "🔄 Restauración de Base de Datos"
echo "================================"
echo ""

# Listar backups disponibles
echo "📋 Backups disponibles:"
ls -lh "$BACKUP_DIR" | grep "backup_${DB_NAME}" | nl
echo ""

# Solicitar archivo de backup
read -p "📁 Nombre del archivo de backup (sin path): " BACKUP_FILE
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILE}"

# Verificar que existe
if [ ! -f "$BACKUP_PATH" ]; then
    echo "❌ Error: Archivo no encontrado: $BACKUP_PATH"
    exit 1
fi

echo ""
echo "⚠️  ADVERTENCIA: Esta operación sobrescribirá la base de datos actual"
echo "📦 Archivo: $BACKUP_FILE"
echo "🗄️  Base de datos: $DB_NAME"
echo ""
read -p "¿Continuar? (escribir 'SI' para confirmar): " CONFIRM

if [ "$CONFIRM" != "SI" ]; then
    echo "❌ Operación cancelada"
    exit 0
fi

# Solicitar password
echo ""
read -sp "🔐 Password de MariaDB para $DB_USER: " DB_PASSWORD
echo ""

# Descomprimir si es necesario
if [[ "$BACKUP_FILE" == *.gz ]]; then
    echo "🗜️  Descomprimiendo backup..."
    gunzip -c "$BACKUP_PATH" > "${BACKUP_PATH%.gz}"
    BACKUP_PATH="${BACKUP_PATH%.gz}"
    TEMP_FILE=true
fi

# Restaurar
echo "🔄 Restaurando base de datos..."
mysql -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" < "$BACKUP_PATH"

# Limpiar archivo temporal
if [ "$TEMP_FILE" = true ]; then
    rm "$BACKUP_PATH"
fi

echo ""
echo "✅ Base de datos restaurada exitosamente"
echo "🎉 Proceso finalizado"

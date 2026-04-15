#!/bin/bash
# ============================================
# Backup de Base de Datos MariaDB
# ============================================
# Script para crear backups antes de migraciones
# o cambios críticos en producción
# ============================================

set -e

# Configuración
BACKUP_DIR="/var/backups/databases/buloneraalvearDB"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="buloneraalvearDB"
DB_USER="bulonera_user"
BACKUP_FILE="${BACKUP_DIR}/backup_${DB_NAME}_${DATE}.sql"

# Crear directorio de backups si no existe
mkdir -p "$BACKUP_DIR"

echo "🔄 Iniciando backup de base de datos..."
echo "📁 Base de datos: $DB_NAME"
echo "📅 Fecha: $(date)"
echo ""

# Solicitar password
read -sp "🔐 Password de MariaDB para $DB_USER: " DB_PASSWORD
echo ""

# Crear backup
echo "💾 Creando backup..."
mysqldump -u "$DB_USER" -p"$DB_PASSWORD" "$DB_NAME" > "$BACKUP_FILE"

# Comprimir backup
echo "🗜️  Comprimiendo backup..."
gzip "$BACKUP_FILE"
BACKUP_FILE="${BACKUP_FILE}.gz"

# Verificar tamaño
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)

echo ""
echo "✅ Backup completado exitosamente"
echo "📦 Archivo: $BACKUP_FILE"
echo "📊 Tamaño: $BACKUP_SIZE"
echo ""

# Listar backups existentes
echo "📋 Backups existentes:"
ls -lh "$BACKUP_DIR" | grep "backup_${DB_NAME}"
echo ""

# Limpiar backups antiguos (mantener últimos 10)
echo "🧹 Limpiando backups antiguos (manteniendo últimos 10)..."
cd "$BACKUP_DIR"
ls -t backup_${DB_NAME}_*.sql.gz | tail -n +11 | xargs -r rm
echo "✅ Limpieza completada"
echo ""

echo "🎉 Proceso finalizado"

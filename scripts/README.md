# 📜 Scripts de Deploy y Mantenimiento

> Colección de scripts para facilitar el deploy y mantenimiento de Bulonera Web en producción

---

## 📋 Índice de Scripts

### 🚀 Deploy
- `deploy.sh` - Script automatizado de deploy completo
- `health_check.sh` - Verificación de estado de todos los servicios

### 💾 Base de Datos
- `backup_database.sh` - Crear backup de MariaDB
- `restore_database.sh` - Restaurar backup de MariaDB
- `fix_mariadb_permissions.sql` - Fix permisos para Docker (SOLO PRIMERA VEZ)
- `migrate_float_to_decimal.sh` - Migración de FloatField a DecimalField

### 🔴 Redis
- `verify_redis_dbs.sh` - Verificar qué DBs usa el ERP

### 🌐 OpenLiteSpeed
- `ols_vhost_config.conf` - Configuración de Virtual Host

---

## 🚀 Scripts de Deploy

### deploy.sh
**Propósito:** Automatizar el proceso completo de deploy

**Uso:**
```bash
cd /var/www/bulonera/web
bash scripts/deploy.sh
```

**Pasos que ejecuta:**
1. Git pull
2. Backup de BD (opcional)
3. Docker build
4. Verificar conexión a BD
5. Aplicar migraciones
6. Collectstatic
7. Restart containers
8. Health check

**Cuándo usar:**
- Deploy de nuevas versiones
- Actualización de código
- Después de cambios en modelos

---

### health_check.sh
**Propósito:** Verificar estado de todos los servicios

**Uso:**
```bash
bash scripts/health_check.sh
```

**Verifica:**
- Docker containers
- MariaDB
- Redis (DBs 3, 4, 5)
- Django (local y público)
- API endpoints
- SSL certificate
- OpenLiteSpeed
- Disk space
- Logs recientes

**Cuándo usar:**
- Después de deploy
- Troubleshooting
- Monitoreo rutinario
- Antes de cambios críticos

---

## 💾 Scripts de Base de Datos

### backup_database.sh
**Propósito:** Crear backup comprimido de MariaDB

**Uso:**
```bash
bash scripts/backup_database.sh
```

**Características:**
- Backup comprimido (.sql.gz)
- Timestamp en nombre de archivo
- Limpieza automática (mantiene últimos 10)
- Guardado en `/var/www/bulonera/backups/`

**Cuándo usar:**
- Antes de migraciones
- Antes de cambios en modelos
- Antes de deploy
- Backup rutinario (cron job)

---

### restore_database.sh
**Propósito:** Restaurar backup de MariaDB

**Uso:**
```bash
bash scripts/restore_database.sh
```

**Características:**
- Lista backups disponibles
- Confirmación antes de restaurar
- Soporte para archivos .gz
- Limpieza de archivos temporales

**Cuándo usar:**
- Recuperación de desastres
- Rollback después de migración fallida
- Restaurar datos perdidos

---

### fix_mariadb_permissions.sql
**Propósito:** Permitir conexiones desde Docker a MariaDB

**Uso:**
```bash
mysql -u root -p < scripts/fix_mariadb_permissions.sql
```

**Qué hace:**
- Cambia permisos de `@'localhost'` a `@'%'`
- Permite conexiones desde subnet Docker (172.x.x.x)
- Flush privileges

**Cuándo usar:**
- SOLO LA PRIMERA VEZ en el VPS
- Si hay error "Can't connect to MySQL server"

**Seguridad:**
- `@'%'` es seguro porque puerto 3306 NO está expuesto a internet
- Verificar con: `sudo ufw status`

---

### migrate_float_to_decimal.sh
**Propósito:** Migrar campos de precio de FloatField a DecimalField

**Uso:**
```bash
bash scripts/migrate_float_to_decimal.sh
```

**Pasos que ejecuta:**
1. Verificar backup reciente (o crear uno)
2. Verificar modelo actual
3. Crear migración
4. Aplicar migración
5. Verificar cambios

**Cuándo usar:**
- Resolver deuda técnica de Fase 4
- Mejorar precisión de precios

**Importante:**
- Requiere backup antes de ejecutar
- Operación irreversible
- Verificar precios después

---

## 🔴 Scripts de Redis

### verify_redis_dbs.sh
**Propósito:** Verificar qué DBs de Redis usa el ERP

**Uso:**
```bash
bash scripts/verify_redis_dbs.sh
```

**Qué hace:**
- Escanea DBs 0-15
- Muestra cantidad de keys por DB
- Lista primeras 5 keys de cada DB
- Recomienda DBs libres para la web

**Cuándo usar:**
- Antes del primer deploy
- Si hay conflictos de Redis
- Para documentar uso de DBs

---

## 🌐 Configuración de OpenLiteSpeed

### ols_vhost_config.conf
**Propósito:** Template de configuración de Virtual Host

**Uso:**
1. Acceder a panel OLS: `https://<vps-ip>:7080`
2. Virtual Hosts → buloneraalvear.online
3. Copiar configuración de este archivo

**Configuración incluida:**
- Proxy a Django (127.0.0.1:8002)
- Static files servidos por OLS
- Media files servidos por OLS
- SSL configuration
- Security headers
- Cache headers
- Rewrite rules (HTTPS redirect)

---

## 📅 Cron Jobs Recomendados

### Backup Diario
```bash
# Backup diario a las 3 AM
0 3 * * * /var/www/bulonera/web/scripts/backup_database.sh >> /var/www/bulonera/logs/backup.log 2>&1
```

### Health Check Cada Hora
```bash
# Health check cada hora
0 * * * * /var/www/bulonera/web/scripts/health_check.sh >> /var/www/bulonera/logs/health.log 2>&1
```

---

## 🔧 Permisos de Scripts

Hacer ejecutables todos los scripts:
```bash
chmod +x scripts/*.sh
```

---

## 📝 Notas Importantes

1. **Backups:** Siempre crear backup antes de cambios críticos
2. **Logs:** Todos los scripts generan logs en `/var/www/bulonera/logs/`
3. **Confirmación:** Scripts críticos requieren confirmación explícita
4. **Colores:** Scripts usan colores para mejor legibilidad
5. **Exit codes:** Scripts retornan 0 en éxito, 1 en error

---

## 🆘 Troubleshooting

### Script no ejecuta
```bash
# Verificar permisos
ls -la scripts/

# Hacer ejecutable
chmod +x scripts/nombre_script.sh
```

### Error de conexión a BD
```bash
# Verificar permisos MariaDB
mysql -u root -p -e "SELECT User, Host FROM mysql.user WHERE User = 'bulonera_user';"

# Si es necesario, ejecutar fix
mysql -u root -p < scripts/fix_mariadb_permissions.sql
```

### Error de Redis
```bash
# Verificar Redis
redis-cli ping

# Verificar DBs
bash scripts/verify_redis_dbs.sh
```

---

**Última actualización:** 5 de Abril de 2026  
**Mantenido por:** Equipo Bulonera Web

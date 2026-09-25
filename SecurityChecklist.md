# 🛡️ Manual de Seguridad y Operaciones — BULONERA WEB

> Documento central de referencia para la seguridad, diagnóstico, mantenimiento y operación de la aplicación web en producción.
> Convive con el ERP en el mismo VPS (Hostinger Ubuntu 24.04). Para el manual del ERP, ver `SecurityChecklist.md` del proyecto ERP.
> Para detalles del código fuente de los scripts, ver [scripts/README.md](scripts/README.md).

---

## 📋 Índice de Contenidos

1. [Datos del Servidor y Arquitectura](#-1-datos-del-servidor-y-arquitectura)
2. [Servicios Docker (Web)](#-2-servicios-docker-web)
3. [Logs y Diagnóstico de Errores](#-3-logs-y-diagnóstico-de-errores)
4. [Redis (Caché y Broker Celery)](#-4-redis-caché-y-broker-celery)
5. [Celery (Tareas Asíncronas)](#-5-celery-tareas-asíncronas)
6. [Base de Datos (MariaDB)](#-6-base-de-datos-mariadb)
7. [Backups de Base de Datos](#-7-backups-de-base-de-datos)
8. [Firewall UFW y Puertos](#-8-firewall-ufw-y-puertos)
9. [Fail2ban (Protección contra Fuerza Bruta)](#-9-fail2ban-protección-contra-fuerza-bruta)
10. [OpenLiteSpeed y Proxy Reverso](#-10-openlitespeed-y-proxy-reverso)
11. [SSH y Llaves de Acceso](#-11-ssh-y-llaves-de-acceso)
12. [SSL/TLS y Headers de Seguridad](#-12-ssltls-y-headers-de-seguridad)
13. [Sistema de Archivos y Permisos](#-13-sistema-de-archivos-y-permisos)
14. [Hardening de Infraestructura (SEC-INF)](#-14-hardening-de-infraestructura-sec-inf)
15. [Scripts de Infraestructura (Referencia Rápida)](#-15-scripts-de-infraestructura-referencia-rápida)
16. [Deploy a Producción](#-16-deploy-a-producción)
17. [Checklist de Auditoría Periódica](#-17-checklist-de-auditoría-periódica)

---

## 🖥️ 1. Datos del Servidor y Arquitectura

| Dato | Valor |
|---|---|
| **IP Pública** | `212.85.12.132` |
| **Dominio Web** | `buloneraalvear.online` |
| **Dominio ERP** | `erp.buloneraalvear.online` |
| **SO** | Ubuntu 24.04 LTS |
| **Proveedor** | Hostinger VPS (2 CPUs, 7.8GB RAM) |
| **Usuario SSH** | `adminbuloneraalvear` |
| **Método de acceso** | Llave pública Ed25519 (contraseñas **deshabilitadas**) |
| **App Web** | `/var/www/bulonera/web_bulonera_alvear/` |
| **App ERP** | `/var/www/erp/src/` |
| **Media Compartida** | `/var/www/shared/media/` (propiedad `www-data:www-data`, `33:33`) |
| **Static Files** | `/var/www/bulonera/staticfiles/` |
| **Logs Web** | `/var/www/bulonera/logs/` |

### Arquitectura de Red (Web)

```
Internet → OLS (:443 HTTPS) → Proxy → 127.0.0.1:8003 (Host) → Docker :8002 (bulonera_web)
                                                                    ↓
                                                               uWSGI (3 workers × 2 threads)
                                                                    ↓
                                                          Django 5.0 (production settings)
                                                                    ↓
                                                     MariaDB (host.docker.internal:3306)
                                                     Redis   (bulonera_web_redis:6379)
```

### Convivencia Web + ERP

Ambas aplicaciones comparten el mismo VPS pero están **completamente aisladas** a nivel de:

| Recurso | Web | ERP |
|---|---|---|
| **Docker Network** | `web_bulonera_alvear_default` | `erp_default` |
| **Contenedor Django** | `bulonera_web_production` (:8003→:8002) | `erp_web` (:8002→:8000) |
| **Base de Datos** | `buloneraalvearDB` / `bulonera_user` | `erp_db` / `erp_user` |
| **Redis** | `bulonera_web_redis` (DBs 3,4,5) | `erp_redis` (DBs 0,1,2) |
| **Logs** | `/var/www/bulonera/logs/` | `/var/www/erp/logs/` |
| **Media** | `/var/www/shared/media/` (compartida) | `/var/www/shared/media/` (compartida) |

---

## 🐳 2. Servicios Docker (Web)

### Contenedores de la Web

| Contenedor | Función | Puerto | Healthcheck |
|---|---|---|---|
| `bulonera_web_production` | Django + uWSGI | `127.0.0.1:8003→8002` | `urllib.request.urlopen('http://localhost:8002/')` |
| `bulonera_web_redis` | Caché + Broker Celery | `6379` (solo red Docker) | `redis-cli ping` |
| `bulonera_web_celery_worker_production` | Procesamiento de imágenes, emails | — | — |
| `bulonera_web_celery_beat_production` | Scheduler de tareas programadas | — | — |
| `bulonera_web_flower_production` | Monitor visual de Celery | `127.0.0.1:5556→5555` | — |

### Comandos esenciales de Docker

```bash
# ====================================================
# Directorio base y compose file
# ====================================================
WEB_DIR="/var/www/bulonera/web_bulonera_alvear"
COMPOSE="docker compose -f $WEB_DIR/docker-compose.production.yml"

# ====================================================
# Estado general
# ====================================================
# Estado rápido (script personalizado)
sudo web_status.sh

# Ver todos los contenedores de la web
$COMPOSE ps

# ====================================================
# Reiniciar servicios
# ====================================================
# Reiniciar todos (sin rebuild)
$COMPOSE restart

# Reiniciar solo un servicio
$COMPOSE restart bulonera_web
$COMPOSE restart bulonera_web_celery_worker

# ====================================================
# Healthchecks individuales
# ====================================================
docker inspect -f '{{.Name}}: {{.State.Health.Status}}' bulonera_web_production bulonera_web_redis

# Chequeo completo de Django
$COMPOSE exec bulonera_web python manage.py check

# Shell de Django interactivo
$COMPOSE exec -it bulonera_web python manage.py shell

# Ver estado de migraciones
$COMPOSE exec bulonera_web python manage.py showmigrations

# Aplicar migraciones en producción (contenedor temporal)
$COMPOSE run --rm bulonera_web python manage.py migrate --no-input

# Collectstatic manual
$COMPOSE run --rm bulonera_web python manage.py collectstatic --no-input
```

---

## 📝 3. Logs y Diagnóstico de Errores

Los logs se persisten en el host mediante volúmenes Docker montados en `/var/www/bulonera/logs/`.

### Ubicación de los logs

| Log | Archivo | Qué registra |
|---|---|---|
| **uWSGI** | `/var/www/bulonera/logs/uwsgi_web.log` | Peticiones HTTP, errores 500, tiempos de respuesta, harakiri |
| **Django** | `/var/www/bulonera/logs/django.log` | Warnings, errores de Django, tracebacks |
| **Celery Worker** | `/var/www/bulonera/logs/celery_worker.log` | Ejecución de tareas asíncronas (imágenes, emails) |
| **Celery Beat** | `/var/www/bulonera/logs/celery_beat.log` | Scheduler de tareas programadas |

### Ver logs en tiempo real

```bash
# uWSGI (el más útil para diagnosticar errores HTTP)
tail -f /var/www/bulonera/logs/uwsgi_web.log

# Django (errores internos y warnings)
tail -f /var/www/bulonera/logs/django.log

# Celery Worker (tareas en background)
tail -f /var/www/bulonera/logs/celery_worker.log

# Ver las últimas 40 líneas sin follow
tail -n 40 /var/www/bulonera/logs/uwsgi_web.log

# Logs del contenedor vía Docker (stdout/stderr)
$COMPOSE logs --tail=40 bulonera_web
$COMPOSE logs --tail=40 bulonera_web_celery_worker
```

### Buscar errores específicos

```bash
# Buscar errores 500 en uWSGI
grep -i "500\|error\|traceback" /var/www/bulonera/logs/uwsgi_web.log | tail -20

# Buscar errores de Celery (tareas fallidas)
grep -i "error\|traceback\|exception" /var/www/bulonera/logs/celery_worker.log | tail -20

# Buscar errores de Django
grep -i "error\|warning\|critical" /var/www/bulonera/logs/django.log | tail -20

# Buscar por fecha específica (hoy)
grep "$(date +%Y-%m-%d)" /var/www/bulonera/logs/uwsgi_web.log | grep -i error
```

### Logs del sistema operativo (compartidos con ERP)

```bash
# Log general del sistema
sudo journalctl -xe --no-pager | tail -50

# Logs de SSH (intentos de acceso)
sudo journalctl -u ssh --since "1 hour ago" --no-pager

# Logs de fail2ban
sudo tail -n 30 /var/log/fail2ban.log

# Logs de UFW (paquetes bloqueados)
sudo grep UFW /var/log/syslog | tail -20
```

---

## 🔴 4. Redis (Caché y Broker Celery)

La Web usa su **propio contenedor Redis** (`bulonera_web_redis`), separado del ERP. La autenticación es obligatoria (`requirepass`).

### Distribución de DBs Redis

| DB | Propósito | Aplicación |
|---|---|---|
| `0`, `1`, `2` | Broker, Results, Cache | ERP (`erp_redis`) |
| `3` | Celery Broker | **Web** (`bulonera_web_redis`) |
| `4` | Celery Result Backend | **Web** (`bulonera_web_redis`) |
| `5` | Django Cache | **Web** (`bulonera_web_redis`) |

### Verificaciones básicas

```bash
# Ping con autenticación
docker exec bulonera_web_redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" ping
# Resultado esperado: PONG

# Ver uso de memoria
docker exec bulonera_web_redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" info memory

# Ver claves almacenadas en caché
docker exec bulonera_web_redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" -n 5 dbsize

# Limpiar toda la caché de Django (¡CUIDADO!)
docker exec bulonera_web_redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" -n 5 flushdb

# Ver clientes conectados
docker exec bulonera_web_redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" client list

# Verificar mensajes pendientes en cola Celery
docker exec bulonera_web_redis redis-cli --no-auth-warning -a "$REDIS_PASSWORD" -n 3 llen celery
```

---

## ⚙️ 5. Celery (Tareas Asíncronas)

Celery se usa para procesamiento de imágenes WebP, envío de emails y tareas programadas.

### Estado y monitoreo

```bash
# Ver estado del worker
docker exec bulonera_web_celery_worker_production celery -A web_bulonera inspect active

# Ver tareas registradas
docker exec bulonera_web_celery_worker_production celery -A web_bulonera inspect registered

# Ver tareas programadas
docker exec bulonera_web_celery_worker_production celery -A web_bulonera inspect scheduled

# Monitor visual Flower (solo accesible desde localhost)
# URL: http://127.0.0.1:5556 (requiere túnel SSH o acceso local)
```

### Reinicio de Workers

```bash
WEB_DIR="/var/www/bulonera/web_bulonera_alvear"
COMPOSE="docker compose -f $WEB_DIR/docker-compose.production.yml"

# Reiniciar solo el worker
$COMPOSE restart bulonera_web_celery_worker

# Reiniciar el scheduler
$COMPOSE restart bulonera_web_celery_beat

# Reiniciar ambos
$COMPOSE restart bulonera_web_celery_worker bulonera_web_celery_beat
```

---

## 🗄️ 6. Base de Datos (MariaDB)

MariaDB corre **directamente en el host** (no en Docker). Los contenedores se conectan vía `host.docker.internal` que resuelve a la IP del host Docker.

### Configuración de Red y Blindaje

| Parámetro | Valor | Verificación |
|---|---|---|
| **Bind Address** | `127.0.0.1,172.17.0.1` | `sudo ss -tulpn \| grep 3306` |
| **Puerto** | `3306` (nunca en `0.0.0.0`) | Solo `localhost` y red Docker |
| **Archivo config** | `/etc/mysql/mariadb.conf.d/50-server.cnf` | — |

### Usuarios y Bases de Datos

| Base de Datos | Usuario | Grants | Aplicación |
|---|---|---|---|
| `buloneraalvearDB` | `bulonera_user` | `172.%`, `%`, `localhost` | Web |
| `erp_db` | `erp_user` | `172.%`, `localhost` | ERP |

### ⚠️ Precauciones con Passwords

> **REGLA CRÍTICA:** Nunca usar caracteres `$` en passwords de BD cuando Docker Compose interpola variables con `env_file`. Docker Compose interpreta `$$` como escape de `$`, causando mismatch silencioso entre la password que envía el contenedor y la que espera MariaDB.

### Comandos de diagnóstico

```bash
# Conectar a la consola de MariaDB
sudo mysql -u root -p

# Ver usuarios y grants de la Web
sudo mysql -e "SELECT User, Host FROM mysql.user WHERE User = 'bulonera_user';"
sudo mysql -e "SHOW GRANTS FOR 'bulonera_user'@'172.%';"

# Ver conexiones activas
sudo mysql -e "SHOW STATUS LIKE 'Threads_connected';"

# Ver procesos en ejecución
sudo mysql -e "SHOW PROCESSLIST;"

# Ver tamaño de la BD Web
sudo mysql -e "SELECT table_schema AS 'Base de Datos', 
  ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'Tamaño (MB)' 
  FROM information_schema.TABLES 
  WHERE table_schema = 'buloneraalvearDB' 
  GROUP BY table_schema;"

# Ver las tablas más pesadas
sudo mysql -e "SELECT table_name, 
  ROUND((data_length + index_length) / 1024 / 1024, 2) AS 'MB' 
  FROM information_schema.TABLES 
  WHERE table_schema = 'buloneraalvearDB' 
  ORDER BY (data_length + index_length) DESC LIMIT 10;"
```

### Reconstruir permisos MariaDB

Si los permisos se corrompen o el contenedor cambia de subred:

```bash
# Usar el script idempotente (reemplazar CAMBIAR_POR_PASSWORD_BD)
sudo mysql -u root -p < /var/www/bulonera/web_bulonera_alvear/scripts/fix_mariadb_permissions.sql
```

---

## 🔐 7. Backups de Base de Datos

Los backups de `buloneraalvearDB` se almacenan en `/var/backups/databases/buloneraalvearDB/`.

> **NOTA:** Los backups cifrados AES-256 son gestionados por el script del ERP (`~/backup_databases.sh`) que cubre ambas bases. El script de la Web (`scripts/backup_database.sh`) es un complemento rápido sin cifrado para pre-migración.

### Backup rápido (pre-migración)

```bash
sudo /var/www/bulonera/web_bulonera_alvear/scripts/backup_database.sh
```

### Backup cifrado completo (ambas BDs)

```bash
sudo ~/backup_databases.sh
```

### Restaurar un backup

```bash
sudo /var/www/bulonera/web_bulonera_alvear/scripts/restore_database.sh
```

### Verificar integridad del último backup cifrado

```bash
cd /var/backups/databases/buloneraalvearDB/
sha256sum -c $(ls -t *.sha256 | head -1)
# Resultado esperado: OK
```

---

## 🧱 8. Firewall UFW y Puertos

El firewall es **compartido con el ERP** y sigue política Zero-Trust (`deny incoming`).

### Puertos permitidos

| Puerto | Protocolo | Acceso | Propósito |
|---|---|---|---|
| `22` | TCP | `LIMIT` (rate-limited) | SSH (solo llaves públicas) |
| `80` | TCP | `ALLOW` | HTTP (redirige a HTTPS) |
| `443` | TCP | `ALLOW` | HTTPS (OLS + TLS 1.3) |
| `3306` | TCP | `ALLOW` solo desde `172.16.0.0/12` | MariaDB (solo red Docker) |
| `7080` | — | **BLOQUEADO por defecto** | OLS Admin (bajo demanda) |

### Verificar estado

```bash
# Estado del firewall
sudo ufw status

# Qué puertos están realmente escuchando
sudo ss -tulpn | grep -E ':(22|80|443|7080|3306|6379|8002|8003)'
```

---

## 🚫 9. Fail2ban (Protección contra Fuerza Bruta)

Fail2ban es **compartido con el ERP**. Ver la sección correspondiente en el SecurityChecklist del ERP.

```bash
# Ver jails activas
sudo fail2ban-client status

# Estado detallado de SSH
sudo fail2ban-client status sshd

# IPs baneadas recientemente
sudo tail -n 20 /var/log/fail2ban.log | grep Ban
```

---

## 🌐 10. OpenLiteSpeed y Proxy Reverso

OLS sirve como proxy reverso para la Web en `:443`, redirigiendo tráfico dinámico a Django vía `http://127.0.0.1:8003`.

### Flujo de Request

```
Cliente → OLS (:443)
           ├── /static/* → /var/www/bulonera/staticfiles/ (directo, cache 1 año)
           ├── /media/*  → /var/www/shared/media/ (directo, cache 1 año)
           └── /*        → proxy → 127.0.0.1:8003 → Docker :8002 → uWSGI → Django
```

### Configuración del VHost

El archivo de referencia es [scripts/ols_vhost_config.conf](scripts/ols_vhost_config.conf). Contiene:

- **Bloqueo de scripts ejecutables** en `/static/` y `/media/` (`.php`, `.py`, `.sh`, `.phar`, `.cgi`, `.pl`, `.bat`, `.exe`)
- **Bloqueo de XSS almacenado** vía archivos `.html`, `.svg`, `.xml` en `/media/`
- **Security Headers** unificados (HSTS, X-Frame-Options, CSP, Permissions-Policy)
- **SSL/TLS** con Let's Encrypt y QUIC/HTTP3 habilitado

### Reiniciar OpenLiteSpeed

```bash
# Reiniciar OLS
sudo /usr/local/lsws/bin/lswsctrl restart

# Verificar estado
systemctl status lsws

# Abrir panel admin temporalmente (60 min)
sudo ols-open

# Cerrar panel admin
sudo ols-close
```

---

## 🔑 11. SSH y Llaves de Acceso

La configuración SSH es **compartida con el ERP**. Ver SecurityChecklist del ERP para procedimientos detallados.

### Configuración activa

| Parámetro | Valor |
|---|---|
| `PasswordAuthentication` | `no` |
| `PubkeyAuthentication` | `yes` |
| `PermitRootLogin` | `no` |
| `MaxAuthTries` | `4` |

### Verificar configuración

```bash
sudo sshd -T | grep -iE 'passwordauthentication|pubkeyauthentication|permitrootlogin'
```

---

## 🔒 12. SSL/TLS y Headers de Seguridad

### Headers de seguridad (doble capa: OLS + Django)

| Header | Valor | Origen |
|---|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | OLS + Django |
| `X-Frame-Options` | `DENY` | OLS + Django |
| `X-Content-Type-Options` | `nosniff` | OLS + Django |
| `X-XSS-Protection` | `1; mode=block` | OLS |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | OLS |
| `Permissions-Policy` | `geolocation=(), microphone=(), camera=()` | OLS |
| `Content-Security-Policy` | Restrictiva (ver `ols_vhost_config.conf`) | OLS |

### Django Production Settings (seguridad)

| Setting | Valor | Referencia |
|---|---|---|
| `SECURE_SSL_REDIRECT` | `True` | [production.py](web_bulonera/settings/production.py) |
| `SECURE_HSTS_SECONDS` | `31536000` | [production.py](web_bulonera/settings/production.py) |
| `SECURE_PROXY_SSL_HEADER` | `('HTTP_X_FORWARDED_PROTO', 'https')` | SEC-010 |
| `SESSION_COOKIE_SECURE` | `True` | [production.py](web_bulonera/settings/production.py) |
| `SESSION_COOKIE_HTTPONLY` | `True` | SEC-010 |
| `SESSION_COOKIE_SAMESITE` | `Lax` | SEC-010 |
| `CSRF_COOKIE_SECURE` | `True` | [production.py](web_bulonera/settings/production.py) |
| `CSRF_TRUSTED_ORIGINS` | `buloneraalvear.online`, `www.` | [production.py](web_bulonera/settings/production.py) |

### Verificaciones SSL

```bash
# Verificar SSL y HSTS
curl -I https://buloneraalvear.online/ | grep -i "Strict-Transport"

# Verificar headers de seguridad
curl -I https://buloneraalvear.online/ | grep -E -i "X-Frame|Content-Type-Options|Referrer-Policy|Permissions-Policy"

# Verificar que .env NO es accesible
curl -I https://buloneraalvear.online/.env | grep "403\|404"
# Resultado esperado: 403 o 404

# Verificar versión TLS
curl -vvv https://buloneraalvear.online/ 2>&1 | grep "TLS\|SSL"
```

---

## 📂 13. Sistema de Archivos y Permisos

### Permisos críticos

| Recurso | Propietario | Permisos | Verificación |
|---|---|---|---|
| `.env` (producción) | `root:root` | `600` | `stat -c "%a" /var/www/bulonera/web_bulonera_alvear/.env` |
| `/var/www/shared/media/` | `www-data:www-data` (33:33) | `755` | `stat -c '%u:%g %U:%G' /var/www/shared/media/` |
| `/var/www/bulonera/logs/` | `www-data:www-data` (33:33) | `755` | `stat -c '%u:%g' /var/www/bulonera/logs/` |
| `/var/www/bulonera/staticfiles/` | `www-data:www-data` | `755` | — |
| Vault key (backups) | `root:root` | `400` | `sudo stat -c "%a" /root/.backup_vault_key` |

### Contenedor: Usuario no-root (SEC-INF-002)

El contenedor Docker ejecuta como `www-data` (UID 33 / GID 33), coincidiendo exactamente con el propietario del directorio de media en el host. Esto se define en [Dockerfile.production](Dockerfile.production):

```dockerfile
RUN chown -R www-data:www-data /app
USER www-data
```

### Verificaciones de disco

```bash
# Espacio en disco
df -h /

# Espacio usado por la web
du -sh /var/www/bulonera/

# Espacio de media compartida
du -sh /var/www/shared/media/

# Espacio de logs
du -sh /var/www/bulonera/logs/

# RAM disponible
free -h

# Carga del sistema
uptime
```

---

## 🔐 14. Hardening de Infraestructura (SEC-INF)

Registro de todas las medidas de hardening aplicadas sobre la infraestructura de producción.

### SEC-INF-001: Validación de Uploads (Modelo)

**Qué:** Validadores `FileExtensionValidator` + `validate_image_file` (magic bytes) en todos los campos `ImageField` de los modelos.
**Dónde:** `account/models.py`, `store/models.py`, `category/models.py`, `media_bank/models.py`
**Por qué:** Previene uploads de archivos maliciosos disfrazados de imágenes.

### SEC-INF-002: Usuario no-root en Docker

**Qué:** El contenedor ejecuta como `www-data` (UID 33), no como `root`.
**Dónde:** [Dockerfile.production](Dockerfile.production)
**Por qué:** Si un atacante logra RCE dentro del contenedor, sus permisos están confinados a `www-data`. Coincide con el propietario de `/var/www/shared/media/` en el host, evitando escalación de privilegios al escribir archivos en volúmenes montados.

### SEC-INF-003: Bloqueo de Ejecución de Scripts en OLS

**Qué:** Reglas `RewriteRule` que devuelven `403 Forbidden` para `.php`, `.py`, `.sh`, `.phar`, `.cgi`, `.pl`, `.bat`, `.exe`, `.html`, `.svg`, `.xml` en `/static/` y `/media/`.
**Dónde:** [scripts/ols_vhost_config.conf](scripts/ols_vhost_config.conf)
**Por qué:** Previene ejecución remota de código y XSS almacenado si un atacante logra subir un archivo malicioso al directorio de media.

### SEC-INF-004: Fail-Closed en Healthchecks y Entrypoint

**Qué:** El `docker-entrypoint.sh` ejecuta `migrate --noinput` antes de arrancar uWSGI. Si la migración falla, el contenedor **no arranca** (fail-closed). El healthcheck en `docker-compose.production.yml` verifica que el endpoint `/` responde.
**Dónde:** [docker-entrypoint.sh](docker-entrypoint.sh), [docker-compose.production.yml](docker-compose.production.yml)
**Por qué:** Evita operar con un schema de BD corrupto o desactualizado.

### SEC-INF-005: Permisos MariaDB Confinados

**Qué:** `bulonera_user` tiene grants para `172.%`, `%` y `localhost` (nunca `0.0.0.0`). MariaDB escucha solo en `127.0.0.1` y `172.17.0.1`.
**Dónde:** [scripts/fix_mariadb_permissions.sql](scripts/fix_mariadb_permissions.sql), `/etc/mysql/mariadb.conf.d/50-server.cnf`
**Por qué:** Defensa en profundidad. Incluso si el firewall falla, MariaDB no acepta conexiones externas.

### SEC-INF-006: Security Headers en OLS

**Qué:** Headers HSTS, X-Frame-Options, CSP, Permissions-Policy inyectados a nivel de web server.
**Dónde:** [scripts/ols_vhost_config.conf](scripts/ols_vhost_config.conf)
**Por qué:** Protección contra clickjacking, MIME sniffing, XSS y framing malicioso.

### SEC-INF-007: Límite de Tamaño de Uploads

**Qué:** `DATA_UPLOAD_MAX_MEMORY_SIZE` y `FILE_UPLOAD_MAX_MEMORY_SIZE` configurados en `base.py`.
**Dónde:** [web_bulonera/settings/base.py](web_bulonera/settings/base.py)
**Por qué:** Previene ataques DoS por uploads masivos.

### SEC-INF-008: Credenciales parametrizadas en Health Check

**Qué:** `health_check.sh` lee `DB_PASSWORD` y `REDIS_PASSWORD` desde `.env` en lugar de hardcodear.
**Dónde:** [scripts/health_check.sh](scripts/health_check.sh)
**Por qué:** Elimina secretos hardcodeados en scripts versionados.

### SEC-INF-009: Redis autenticado

**Qué:** `requirepass` obligatorio en Redis con password leída de `$REDIS_PASSWORD`.
**Dónde:** [docker-compose.production.yml](docker-compose.production.yml)
**Por qué:** Previene acceso no autorizado al broker de Celery y la caché.

---

## 🧰 15. Scripts de Infraestructura (Referencia Rápida)

| Script | Ubicación | Ejecución | Función |
|---|---|---|---|
| `deploy.sh` | `scripts/deploy.sh` | `/var/www/bulonera/web_bulonera_alvear/scripts/deploy.sh` | Deploy completo: git pull + build + migrate + collectstatic + restart + verify |
| `web_status.sh` | `scripts/web_status.sh` | `sudo web_status.sh` | Diagnóstico rápido: Docker, HTTP, Redis, MariaDB, disco, RAM, logs |
| `health_check.sh` | `scripts/health_check.sh` | `sudo /var/www/bulonera/web_bulonera_alvear/scripts/health_check.sh` | Verificación exhaustiva: Docker, DB, Redis, HTTP, SSL, OLS, disco |
| `backup_database.sh` | `scripts/backup_database.sh` | `sudo scripts/backup_database.sh` | Backup rápido comprimido (pre-migración) |
| `restore_database.sh` | `scripts/restore_database.sh` | `sudo scripts/restore_database.sh` | Restauración interactiva con confirmación |
| `fix_mariadb_permissions.sql` | `scripts/fix_mariadb_permissions.sql` | `sudo mysql -u root -p < scripts/fix_mariadb_permissions.sql` | Recrear grants idempotente |
| `ols_vhost_config.conf` | `scripts/ols_vhost_config.conf` | Referencia para OLS Admin | Configuración de VHost OLS con security headers |
| `verify_redis_dbs.sh` | `scripts/verify_redis_dbs.sh` | `scripts/verify_redis_dbs.sh` | Verificar separación de DBs Redis |

---

## 🚀 16. Deploy a Producción

### Procedimiento estándar

```bash
# 1. Desde la PC local: push a GitHub
git add .
git commit -m "feat(scope): descripción"
git push

# 2. En el servidor: ejecutar deploy
/var/www/bulonera/web_bulonera_alvear/scripts/deploy.sh
```

El script `deploy.sh` ejecuta automáticamente:
1. `git fetch + reset --hard` (código)
2. `docker compose build` (imagen)
3. `docker compose run --rm migrate` (migraciones)
4. `docker compose run --rm collectstatic` (estáticos)
5. `docker compose up -d` (servicios)
6. `restart celery_worker celery_beat` (recarga código)
7. Verificación SEO de slugs (opcional)
8. Health check HTTP (30s timeout)
9. Estado final de contenedores

### Post-deploy: Verificación manual

```bash
# Verificar respuesta HTTP
curl -I https://buloneraalvear.online/

# Verificar API
curl https://buloneraalvear.online/api/v1/store/products/ | head -20

# Estado completo
sudo web_status.sh

# Reiniciar OLS si cambiaron archivos estáticos cacheados
sudo /usr/local/lsws/bin/lswsctrl restart
```

---

## ✅ 17. Checklist de Auditoría Periódica

Ejecutar estos comandos periódicamente (semanal o quincenal) para verificar la salud del sistema.

### Salud General

```bash
# 1. Estado de contenedores Docker
docker compose -f /var/www/bulonera/web_bulonera_alvear/docker-compose.production.yml ps

# 2. Healthchecks
docker inspect -f '{{.Name}}: {{.State.Health.Status}}' bulonera_web_production bulonera_web_redis

# 3. Chequeo de Django
docker compose -f /var/www/bulonera/web_bulonera_alvear/docker-compose.production.yml exec bulonera_web python manage.py check

# 4. Migraciones al día
docker compose -f /var/www/bulonera/web_bulonera_alvear/docker-compose.production.yml exec bulonera_web python manage.py showmigrations | grep "\[ \]" && echo "⚠️ Pendientes!" || echo "✅ OK"

# 5. Estado rápido
sudo web_status.sh
```

### Seguridad Perimetral (compartida con ERP)

```bash
# 6. Firewall — verificar que solo 22, 80, 443 están abiertos a WAN
sudo ufw status

# 7. OLS Admin cerrado
sudo ufw status | grep 7080 || echo "✅ Puerto 7080 bloqueado"

# 8. SSH no acepta contraseñas
sudo sshd -T | grep -E "passwordauthentication|permitrootlogin"
# Esperado: passwordauthentication no, permitrootlogin no

# 9. MariaDB blindado (nunca 0.0.0.0)
sudo ss -tulpn | grep 3306
# Esperado: 127.0.0.1:3306 y 172.17.0.1:3306

# 10. Fail2ban activo
sudo fail2ban-client status

# 11. IPs baneadas recientemente
sudo tail -n 20 /var/log/fail2ban.log | grep Ban
```

### Integridad de Datos

```bash
# 12. Ejecutar backup
sudo ~/backup_databases.sh

# 13. Verificar integridad del último backup cifrado
cd /var/backups/databases/buloneraalvearDB/ && sha256sum -c $(ls -t *.sha256 | head -1)

# 14. Espacio en disco
df -h /

# 15. Espacio de backups
du -sh /var/backups/databases/

# 16. Permisos del .env
stat -c "%a" /var/www/bulonera/web_bulonera_alvear/.env
# Esperado: 600

# 17. Permisos de media
stat -c '%u:%g %U:%G' /var/www/shared/media/
# Esperado: 33:33 www-data:www-data

# 18. Vault key
sudo stat -c "%a" /root/.backup_vault_key
# Esperado: 400
```

### Seguridad Web (específico)

```bash
# 19. Headers de seguridad
curl -s -I https://buloneraalvear.online/ | grep -E -i "Strict-Transport|X-Frame|X-Content-Type|Referrer-Policy"

# 20. SSL válido
echo | openssl s_client -connect buloneraalvear.online:443 -servername buloneraalvear.online 2>/dev/null | openssl x509 -noout -enddate
# Verificar que no esté por vencer

# 21. .env inaccesible desde web
curl -s -o /dev/null -w "%{http_code}" https://buloneraalvear.online/.env
# Esperado: 403 o 404

# 22. Docker ejecuta como www-data (no root)
docker exec bulonera_web_production whoami
# Esperado: www-data

# 23. Contenedor no tiene root
docker exec bulonera_web_production id
# Esperado: uid=33(www-data) gid=33(www-data)
```

---

*Este documento debe ser auditado periódicamente y es mantenido por el **Auditor de Producción e Infraestructura**.*
*Última actualización: Septiembre 2026 — Deploy exitoso con Hardening SEC-INF-001 a SEC-INF-009, usuario no-root www-data, uWSGI optimizado, Redis separado, MariaDB confinado, OLS con Security Headers y CSP.*

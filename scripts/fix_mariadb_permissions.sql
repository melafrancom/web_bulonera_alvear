-- ============================================
-- FIX CRÍTICO: Permisos MariaDB para Docker
-- ============================================
-- Problema: El usuario bulonera_user fue creado con @'localhost'
-- MariaDB rechaza conexiones desde la IP Docker (172.x.x.x)
-- 
-- Solución: Permitir conexiones desde cualquier IP con @'%'
-- 
-- SEGURIDAD: @'%' es seguro porque el puerto 3306 NO debe estar
-- expuesto a internet. Verificar con: sudo ufw status
-- 
-- Ejecutar SOLO LA PRIMERA VEZ en el VPS:
-- mysql -u root -p < fix_mariadb_permissions.sql
-- ============================================

-- Otorgar permisos desde cualquier IP
GRANT ALL PRIVILEGES ON buloneraalvearDB.* TO 'bulonera_user'@'%' IDENTIFIED BY 'CAMBIAR_POR_PASSWORD_BD';

-- Aplicar cambios
FLUSH PRIVILEGES;

-- Verificar permisos
SELECT User, Host FROM mysql.user WHERE User = 'bulonera_user';

-- Verificar acceso a la base de datos
SHOW GRANTS FOR 'bulonera_user'@'%';

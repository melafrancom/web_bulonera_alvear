-- ============================================
-- FIX: Permisos MariaDB Confinados para Docker (SEC-INF-005)
-- ============================================
-- REGLA: Confinar acceso exclusivamente a la subred de Docker (172.%.%.%) y localhost.
-- Previene que un error en el firewall (UFW/iptables) exponga la DB si el puerto 3306 escucha en 0.0.0.0.
--
-- Ejecutar en el VPS:
-- mysql -u root -p < fix_mariadb_permissions.sql
-- ============================================

-- Eliminar el usuario con comodín global '%' si existía (idempotente)
DROP USER IF EXISTS 'bulonera_user'@'%';

-- Otorgar permisos EXCLUSIVAMENTE desde subred Docker (172.x.x.x) y localhost
GRANT ALL PRIVILEGES ON buloneraalvearDB.* TO 'bulonera_user'@'172.%.%.%' IDENTIFIED BY 'CAMBIAR_POR_PASSWORD_BD';
GRANT ALL PRIVILEGES ON buloneraalvearDB.* TO 'bulonera_user'@'localhost' IDENTIFIED BY 'CAMBIAR_POR_PASSWORD_BD';

-- Aplicar cambios
FLUSH PRIVILEGES;

-- Verificar permisos
SELECT User, Host FROM mysql.user WHERE User = 'bulonera_user';

-- Verificar accesos a la base de datos
SHOW GRANTS FOR 'bulonera_user'@'172.%.%.%';
SHOW GRANTS FOR 'bulonera_user'@'localhost';

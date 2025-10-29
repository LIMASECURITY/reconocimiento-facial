-- 1. CREACIÓN DE BASE DE DATOS Y USUARIO
-- Crea la base de datos para el sistema de reconocimiento facial
CREATE DATABASE facial_recognition_db;

-- Crea un usuario específico con contraseña segura para la aplicación
CREATE USER 'facial_user'@'localhost' IDENTIFIED BY 'NuevaPasswordSegura2024!';
-- Otorga todos los privilegios sobre la base de datos al usuario creado
GRANT ALL PRIVILEGES ON facial_recognition_db.* TO 'facial_user'@'localhost';
-- Actualiza los privilegios para que surtan efecto inmediatamente
FLUSH PRIVILEGES;

-- DesactivarSafeupdatetemporalmente
SET SQL_SAFE_UPDATES = 0;

use facial_recognition_db;

-- 2. CONSULTAS DE MONITOREO
-- Selecciona todas las tablas existentes en la base de datos
SHOW TABLES;

-- Consulta todos los usuarios registrados en el sistema
SELECT * FROM usuarios;

delete from usuarios;
-- Obtiene todos los accesos registrados en el día actual
SELECT * FROM accesos WHERE DATE(fecha_acceso) = CURDATE();

-- 3. REPORTE COMBINADO
-- Muestra un reporte de los últimos 10 accesos con información de usuarios
SELECT 
    a.fecha_acceso,
    a.nombre_usuario,
    a.tipo_acceso,
    a.similitud,
    u.fecha_registro
FROM accesos a
LEFT JOIN usuarios u ON a.nombre_usuario = u.nombre
ORDER BY a.fecha_acceso DESC
LIMIT 10;

-- 4. MONITOREO DE ACCESOS DENEGADOS
-- Consulta los últimos 10 accesos denegados para análisis de seguridad
SELECT * FROM accesos 
WHERE tipo_acceso = 'DENEGADO' 
ORDER BY fecha_acceso DESC 
LIMIT 10;

-- 5. MANTENIMIENTO
-- Elimina todos los registros de acceso del día actual (limpieza)
DELETE FROM accesos WHERE DATE(fecha_acceso) = CURDATE();
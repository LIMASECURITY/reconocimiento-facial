import mysql.connector
from mysql.connector import Error
from datetime import datetime
import config

class DatabaseManager:
    def __init__(self):
        self.db_config = config.DB_CONFIG
    
    def test_connection(self):
        """Verifica que la base de datos esté disponible"""
        try:
            conn = mysql.connector.connect(**self.db_config)
            if conn.is_connected():
                print("✅ Base de datos MySQL disponible")
                conn.close()
                return True
        except Error as e:
            print(f"❌ Error conectando a MySQL: {e}")
        return False
    
    def get_connection(self):
        """Obtiene una nueva conexión a la base de datos"""
        try:
            conn = mysql.connector.connect(**self.db_config)
            return conn
        except Error as e:
            print(f"❌ Error obteniendo conexión MySQL: {e}")
            return None

    def create_user_table(self):
        """Crea o actualiza la tabla de usuarios con contraseña si no existe"""
        conn = self.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            
            # Primero verificar si la tabla existe y tiene las columnas necesarias
            cursor.execute("""
                SELECT COLUMN_NAME 
                FROM INFORMATION_SCHEMA.COLUMNS 
                WHERE TABLE_NAME = 'usuarios' AND TABLE_SCHEMA = %s
            """, (self.db_config['database'],))
            
            existing_columns = [row[0] for row in cursor.fetchall()]
            
            # Si la tabla no existe, crearla
            if not existing_columns:
                cursor.execute("""
                    CREATE TABLE usuarios (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        nombre VARCHAR(100) NOT NULL UNIQUE,
                        password_hash VARCHAR(255) NOT NULL,
                        fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
                        activo BOOLEAN DEFAULT TRUE,
                        ultimo_acceso DATETIME,
                        rol ENUM('user', 'admin') DEFAULT 'user'
                    )
                """)
                print("✅ Tabla de usuarios creada con nuevas columnas")
            else:
                # Si la tabla existe, agregar las columnas que faltan
                if 'password_hash' not in existing_columns:
                    cursor.execute("ALTER TABLE usuarios ADD COLUMN password_hash VARCHAR(255) NOT NULL DEFAULT 'temp_password'")
                    print("✅ Columna password_hash agregada")
                
                if 'rol' not in existing_columns:
                    cursor.execute("ALTER TABLE usuarios ADD COLUMN rol ENUM('user', 'admin') DEFAULT 'user'")
                    print("✅ Columna rol agregada")
            
            # Asegurar que el administrador exista
            cursor.execute("SELECT id FROM usuarios WHERE nombre = 'admin'")
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO usuarios (nombre, password_hash, rol) 
                    VALUES ('admin', '123456798', 'admin')
                """)
                print("✅ Usuario administrador creado")
            else:
                # Actualizar el usuario admin existente si es necesario
                cursor.execute("""
                    UPDATE usuarios 
                    SET password_hash = '123456798', rol = 'admin' 
                    WHERE nombre = 'admin'
                """)
            
            conn.commit()
            print("✅ Tabla de usuarios configurada correctamente")
            return True
            
        except Error as e:
            print(f"❌ Error configurando tabla de usuarios: {e}")
            return False
        finally:
            if conn and conn.is_connected():
                conn.close()

    def create_tables(self):
        """Crea las tablas necesarias"""
        conn = self.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            
            # Primero crear tabla de usuarios si no existe
            self.create_user_table()
            
            # Luego crear tabla de accesos
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS accesos (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    usuario_id INT NULL,
                    nombre_usuario VARCHAR(100) NOT NULL,
                    tipo_acceso ENUM('PERMITIDO', 'DENEGADO') NOT NULL,
                    fecha_acceso DATETIME DEFAULT CURRENT_TIMESTAMP,
                    similitud FLOAT,
                    imagen_path VARCHAR(255),
                    confianza FLOAT,
                    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
                )
            """)
            
            conn.commit()
            print("✅ Tablas creadas/verificadas exitosamente")
            return True
            
        except Error as e:
            print(f"❌ Error creando tablas: {e}")
            return False
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def register_new_user(self, username, password):
        """Registra un nuevo usuario en el sistema"""
        conn = self.get_connection()
        if not conn:
            return False, "Error de conexión a la base de datos"
            
        try:
            cursor = conn.cursor()
            
            # Verificar si el usuario ya existe
            cursor.execute("SELECT id FROM usuarios WHERE nombre = %s", (username,))
            if cursor.fetchone():
                return False, "El nombre de usuario ya existe"
            
            # Registrar nuevo usuario
            cursor.execute("""
                INSERT INTO usuarios (nombre, password_hash, rol) 
                VALUES (%s, %s, 'user')
            """, (username, password))  # En una aplicación real, deberías hashear la contraseña
            
            conn.commit()
            return True, f"Usuario '{username}' registrado exitosamente"
            
        except Error as e:
            return False, f"Error registrando usuario: {e}"
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def verify_user_credentials(self, username, password):
        """Verifica las credenciales de un usuario"""
        conn = self.get_connection()
        if not conn:
            return False, None
            
        try:
            cursor = conn.cursor(dictionary=True)
            
            cursor.execute("""
                SELECT id, nombre, password_hash, rol 
                FROM usuarios 
                WHERE nombre = %s AND activo = TRUE
            """, (username,))
            
            user = cursor.fetchone()
            
            if not user:
                return False, None
            
            # En una aplicación real, deberías verificar el hash de la contraseña
            # Por ahora, comparamos directamente (esto es solo para desarrollo)
            if user['password_hash'] == password:
                return True, user
            else:
                return False, None
                
        except Error as e:
            print(f"❌ Error verificando credenciales: {e}")
            return False, None
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def get_user_id(self, username):
        """Obtiene ID de usuario desde la DB"""
        conn = self.get_connection()
        if not conn:
            return None
            
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM usuarios WHERE nombre = %s", (username,))
            result = cursor.fetchone()
            return result[0] if result else None
        except Error as e:
            print(f"❌ Error obteniendo ID de usuario: {e}")
            return None
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def sync_user(self, username):
        """Sincroniza usuario con la base de datos (para compatibilidad con versiones anteriores)"""
        conn = self.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM usuarios WHERE nombre = %s", (username,))
            if not cursor.fetchone():
                # Verificar qué columnas existen
                cursor.execute("""
                    SELECT COLUMN_NAME 
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = 'usuarios' AND TABLE_SCHEMA = %s AND COLUMN_NAME = 'password_hash'
                """, (self.db_config['database'],))
                
                has_password_column = cursor.fetchone() is not None
                
                if has_password_column:
                    # Nueva estructura con password_hash
                    cursor.execute(
                        "INSERT INTO usuarios (nombre, password_hash, fecha_registro) VALUES (%s, %s, %s)",
                        (username, 'temp_password', datetime.now())
                    )
                else:
                    # Estructura antigua sin password_hash
                    cursor.execute(
                        "INSERT INTO usuarios (nombre, fecha_registro) VALUES (%s, %s)",
                        (username, datetime.now())
                    )
                
                conn.commit()
                print(f"👤 Usuario '{username}' agregado a DB")
                return True
            return True
                
        except Error as e:
            print(f"❌ Error sincronizando usuario: {e}")
            return False
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def log_access(self, usuario_id, nombre_usuario, tipo_acceso, similitud, imagen_path):
        """Registra acceso en la base de datos"""
        conn = self.get_connection()
        if not conn:
            return False
            
        try:
            cursor = conn.cursor()
            
            # Asegurar que similitud sea float nativo
            if hasattr(similitud, 'item'):
                similitud_db = similitud.item()
            else:
                similitud_db = float(similitud)
            
            cursor.execute("""
                INSERT INTO accesos 
                (usuario_id, nombre_usuario, tipo_acceso, similitud, imagen_path, fecha_acceso)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (usuario_id, nombre_usuario, tipo_acceso, similitud_db, imagen_path, datetime.now()))
            
            if tipo_acceso == 'PERMITIDO' and usuario_id:
                cursor.execute(
                    "UPDATE usuarios SET ultimo_acceso = %s WHERE id = %s",
                    (datetime.now(), usuario_id)
                )
            
            conn.commit()
            print("📊 Acceso registrado en la base de datos")
            return True
            
        except Error as e:
            print(f"❌ Error registrando acceso: {e}")
            return False
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def get_access_history(self, limit=10):
        """Obtiene historial de accesos"""
        conn = self.get_connection()
        if not conn:
            return []
            
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT a.*, u.nombre as nombre_completo
                FROM accesos a
                LEFT JOIN usuarios u ON a.usuario_id = u.id
                ORDER BY a.fecha_acceso DESC
                LIMIT %s
            """, (limit,))
            
            return cursor.fetchall()
        except Error as e:
            print(f"❌ Error obteniendo historial: {e}")
            return []
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def get_user_access_history(self, username):
        """Obtiene historial de accesos de un usuario específico"""
        conn = self.get_connection()
        if not conn:
            return []
            
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tipo_acceso, fecha_acceso, similitud
                FROM accesos 
                WHERE nombre_usuario = %s
                ORDER BY fecha_acceso DESC
            """, (username,))
            
            return cursor.fetchall()
        except Error as e:
            print(f"❌ Error obteniendo historial de usuario: {e}")
            return []
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def get_last_user_access(self, username):
        """Obtiene el último acceso de un usuario"""
        conn = self.get_connection()
        if not conn:
            return None
            
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT tipo_acceso, fecha_acceso, similitud
                FROM accesos 
                WHERE nombre_usuario = %s
                ORDER BY fecha_acceso DESC
                LIMIT 1
            """, (username,))
            
            return cursor.fetchone()
        except Error as e:
            print(f"❌ Error obteniendo último acceso: {e}")
            return None
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def get_all_users(self):
        """Obtiene todos los usuarios registrados"""
        conn = self.get_connection()
        if not conn:
            return []
            
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT id, nombre, fecha_registro, ultimo_acceso, activo, rol
                FROM usuarios 
                ORDER BY nombre
            """)
            
            return cursor.fetchall()
        except Error as e:
            print(f"❌ Error obteniendo usuarios: {e}")
            return []
        finally:
            if conn and conn.is_connected():
                conn.close()
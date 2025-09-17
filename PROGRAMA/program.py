import cv2
import numpy as np
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime
import time
import mysql.connector
from mysql.connector import Error
import speech_recognition as sr
import pyttsx3
import webbrowser
import threading
import http.server
import socketserver
import json
import csv
from urllib.parse import parse_qs
from io import StringIO

class FacialRecognitionDB:
    def __init__(self):
        self.known_faces_dir = "usuarios_autorizados"
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.known_faces = {}
        self.web_server = None
        
        # Configuración de MySQL
        self.db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': '123456798',
            'database': 'facial_recognition_db'
        }
        
        self.db_connection = self.create_db_connection()
        if self.db_connection:
            self.create_tables()
            self.load_known_faces()
        else:
            print("❌ No se pudo establecer conexión con la base de datos.")
    
    def setup_voice_engine(self):
        """Configura el motor de voz"""
        try:
            engine = pyttsx3.init()
            voices = engine.getProperty('voices')
            
            # Configurar voz en español si está disponible
            for voice in voices:
                if 'spanish' in voice.name.lower() or 'español' in voice.name.lower():
                    engine.setProperty('voice', voice.id)
                    break
            
            engine.setProperty('rate', 150)  # Velocidad de habla
            return engine
        except Exception as e:
            print(f"❌ Error configurando el motor de voz: {e}")
            return None
    def create_db_connection(self):
        """Crea conexión a MySQL con manejo de errores"""
        try:
            print("🔗 Intentando conectar a MySQL...")
            connection = mysql.connector.connect(**self.db_config)
            
            if connection.is_connected():
                db_info = connection.get_server_info()
                print(f"✅ Conectado a MySQL Server v{db_info}")
                return connection
                
        except Error as e:
            print(f"❌ Error conectando a MySQL: {e}")
            return None

    def create_tables(self):
        """Crea las tablas necesarias"""
        try:
            cursor = self.db_connection.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nombre VARCHAR(100) NOT NULL UNIQUE,
                    fecha_registro DATETIME DEFAULT CURRENT_TIMESTAMP,
                    activo BOOLEAN DEFAULT TRUE,
                    ultimo_acceso DATETIME
                )
            """)
            
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
            
            self.db_connection.commit()
            print("✅ Tablas creadas exitosamente")
            
        except Error as e:
            print(f"❌ Error creando tablas: {e}")
    
    def load_known_faces(self):
        """Carga rostros conocidos"""
        self.known_faces = {}
        
        if not os.path.exists(self.known_faces_dir):
            os.makedirs(self.known_faces_dir)
            print(f"📁 Carpeta '{self.known_faces_dir}' creada.")
            return
        
        print("🔄 Cargando rostros conocidos...")
        
        for filename in os.listdir(self.known_faces_dir):
            if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                name = os.path.splitext(filename)[0]
                path = os.path.join(self.known_faces_dir, filename)
                
                self.sync_user_to_db(name)
                
                img = cv2.imread(path)
                if img is not None:
                    self.known_faces[name] = {
                        'path': path,
                        'features': self.extract_advanced_features(img)
                    }
                    print(f"✅ {name}")
    
    def sync_user_to_db(self, username):
        """Sincroniza usuario con la base de datos"""
        if not self.db_connection:
            return
            
        try:
            cursor = self.db_connection.cursor()
            
            cursor.execute("SELECT id FROM usuarios WHERE nombre = %s", (username,))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO usuarios (nombre, fecha_registro) VALUES (%s, %s)",
                    (username, datetime.now())
                )
                self.db_connection.commit()
                print(f"👤 Usuario '{username}' agregado a DB")
                
        except Error as e:
            print(f"❌ Error sincronizando usuario: {e}")

    def extract_advanced_features(self, image):
        """Extrae características del rostro"""
        if image is None:
            return None
        
        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            
            faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
            
            if len(faces) > 0:
                x, y, w, h = faces[0]
                face_roi = gray[y:y+h, x:x+w]
                face_roi = cv2.resize(face_roi, (200, 200))
                
                hist = cv2.calcHist([face_roi], [0], None, [256], [0, 256])
                hist = cv2.normalize(hist, hist).flatten()
                
                return hist
            
            return None
            
        except Exception as e:
            print(f"❌ Error extrayendo características: {e}")
            return None

    def compare_faces(self, features1, features2):
        """Compara características faciales y devuelve float nativo"""
        if features1 is None or features2 is None:
            return 0.0
        
        min_len = min(len(features1), len(features2))
        feat1 = features1[:min_len]
        feat2 = features2[:min_len]
        
        dot_product = np.dot(feat1, feat2)
        norm1 = np.linalg.norm(feat1)
        norm2 = np.linalg.norm(feat2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        
        # Convertir a float nativo de Python
        if hasattr(similarity, 'item'):
            return max(0.0, similarity.item())
        else:
            return max(0.0, float(similarity))

    def capture_face(self):
        """Captura rostro desde cámara"""
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            print("❌ No se puede acceder a la cámara")
            return None
        
        print("\n📷 Mire a la cámara...")
        print("🟢 Presione ESPACIO para capturar")
        print("🔴 Presione Q para cancelar")
        
        captured_frame = None
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
            
            display_frame = frame.copy()
            
            for (x, y, w, h) in faces:
                cv2.rectangle(display_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            cv2.putText(display_frame, "ESPACIO: Capturar - Q: Cancelar", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            
            cv2.imshow('Reconocimiento Facial', display_frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord(' '):
                captured_frame = frame.copy()
                print("✅ Foto capturada")
                break
            elif key == ord('q'):
                print("❌ Captura cancelada")
                break
        
        cap.release()
        cv2.destroyAllWindows()
        return captured_frame

    def log_access(self, usuario_id, nombre_usuario, tipo_acceso, similitud, imagen_path):
        """Registra acceso en la base de datos"""
        if not self.db_connection:
            return
            
        try:
            cursor = self.db_connection.cursor()
            
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
            
            self.db_connection.commit()
            print("📊 Acceso registrado en la base de datos")
            
        except Error as e:
            print(f"❌ Error registrando acceso: {e}")

    def get_user_id(self, username):
        """Obtiene ID de usuario desde la DB"""
        if not self.db_connection:
            return None
            
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("SELECT id FROM usuarios WHERE nombre = %s", (username,))
            result = cursor.fetchone()
            return result[0] if result else None
        except Error as e:
            print(f"❌ Error obteniendo ID de usuario: {e}")
            return None

    def get_access_history(self, limit=10):
        """Obtiene historial de accesos"""
        if not self.db_connection:
            return []
            
        try:
            cursor = self.db_connection.cursor(dictionary=True)
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

    def show_database_data(self):
        """Muestra todos los datos de la base de datos"""
        if not self.db_connection:
            print("❌ No hay conexión a la base de datos")
            return
        
        try:
            cursor = self.db_connection.cursor()
            
            print("\n" + "="*60)
            print("📊 DATOS COMPLETOS DE LA BASE DE DATOS")
            print("="*60)
            
            print("\n👥 USUARIOS REGISTRADOS:")
            print("-" * 40)
            cursor.execute("SELECT id, nombre, fecha_registro, ultimo_acceso FROM usuarios")
            usuarios = cursor.fetchall()
            
            if usuarios:
                for user in usuarios:
                    print(f"ID: {user[0]} | Nombre: {user[1]} | Registro: {user[2]} | Último acceso: {user[3]}")
            else:
                print("No hay usuarios registrados")
            
            print("\n📋 HISTORIAL DE ACCESOS:")
            print("-" * 60)
            cursor.execute("""
                SELECT a.id, a.nombre_usuario, a.tipo_acceso, a.fecha_acceso, a.similitud
                FROM accesos a
                ORDER BY a.fecha_acceso DESC
                LIMIT 20
            """)
            accesos = cursor.fetchall()
            
            if accesos:
                for acceso in accesos:
                    similitud = acceso[4]
                    if hasattr(similitud, 'item'):
                        similitud = similitud.item()
                    print(f"{acceso[3]} | {acceso[1]} | {acceso[2]} | Similitud: {similitud or 'N/A'}")
            else:
                print("No hay registros de acceso")
            
            print("\n📈 ESTADÍSTICAS:")
            print("-" * 30)
            
            cursor.execute("SELECT COUNT(*) FROM usuarios")
            total_usuarios = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM accesos")
            total_accesos = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM accesos WHERE tipo_acceso = 'PERMITIDO'")
            accesos_permitidos = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM accesos WHERE tipo_acceso = 'DENEGADO'")
            accesos_denegados = cursor.fetchone()[0]
            
            print(f"Total usuarios: {total_usuarios}")
            print(f"Total accesos: {total_accesos}")
            print(f"Accesos permitidos: {accesos_permitidos}")
            print(f"Accesos denegados: {accesos_denegados}")
            
            if total_accesos > 0:
                porcentaje_exito = (accesos_permitidos / total_accesos) * 100
                print(f"Porcentaje de éxito: {porcentaje_exito:.1f}%")
                
        except Exception as e:
            print(f"❌ Error mostrando datos: {e}")

    def export_to_text_file(self):
        """Exporta todos los datos a un archivo de texto"""
        try:
            cursor = self.db_connection.cursor()
            
            with open('reporte_accesos.txt', 'w', encoding='utf-8') as f:
                f.write("="*60 + "\n")
                f.write("REPORTE SISTEMA DE RECONOCIMIENTO FACIAL\n")
                f.write("="*60 + "\n")
                f.write(f"Generado: {datetime.now()}\n\n")
                
                f.write("👥 USUARIOS REGISTRADOS:\n")
                f.write("-" * 40 + "\n")
                cursor.execute("SELECT nombre, fecha_registro, ultimo_acceso FROM usuarios")
                usuarios = cursor.fetchall()
                
                for user in usuarios:
                    f.write(f"Nombre: {user[0]} | Registro: {user[1]} | Último acceso: {user[2]}\n")
                
                f.write("\n📋 ÚLTIMOS ACCESOS:\n")
                f.write("-" * 50 + "\n")
                cursor.execute("""
                    SELECT nombre_usuario, tipo_acceso, fecha_acceso, similitud
                    FROM accesos 
                    ORDER BY fecha_acceso DESC 
                    LIMIT 30
                """)
                accesos = cursor.fetchall()
                
                for acceso in accesos:
                    similitud = acceso[3]
                    if hasattr(similitud, 'item'):
                        similitud = similitud.item()
                    f.write(f"{acceso[2]} | {acceso[0]} | {acceso[1]} | Similitud: {similitud or 'N/A'}\n")
                
                f.write("\n📈 ESTADÍSTICAS:\n")
                f.write("-" * 30 + "\n")
                
                cursor.execute("SELECT COUNT(*) FROM usuarios")
                f.write(f"Total usuarios: {cursor.fetchone()[0]}\n")
                
                cursor.execute("SELECT COUNT(*) FROM accesos")
                f.write(f"Total accesos: {cursor.fetchone()[0]}\n")
                
                cursor.execute("SELECT COUNT(*) FROM accesos WHERE tipo_acceso = 'PERMITIDO'")
                f.write(f"Accesos permitidos: {cursor.fetchone()[0]}\n")
                
                cursor.execute("SELECT COUNT(*) FROM accesos WHERE tipo_acceso = 'DENEGADO'")
                f.write(f"Accesos denegados: {cursor.fetchone()[0]}\n")
            
            print("✅ Reporte exportado a 'reporte_accesos.txt'")
            
        except Exception as e:
            print(f"❌ Error exportando reporte: {e}")

    def voice_search_user(self):
        """Búsqueda de usuario por voz"""
        recognizer = sr.Recognizer()
        microphone = sr.Microphone()
        
        print("🎤 Habla el nombre del usuario que deseas buscar...")
        
        try:
            with microphone as source:
                print("🔇 Silencio, calibrando micrófono...")
                recognizer.adjust_for_ambient_noise(source, duration=1)
                print("✅ Listo para escuchar...")
                
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=5)
            
            print("🔊 Procesando audio...")
            username = recognizer.recognize_google(audio, language="es-ES")
            print(f"🔍 Buscando: {username}")
            
            return username.strip().lower()
            
        except sr.WaitTimeoutError:
            print("❌ Tiempo de espera agotado. No se detectó voz.")
        except sr.UnknownValueError:
            print("❌ No se pudo entender el audio.")
        except sr.RequestError as e:
            print(f"❌ Error en el servicio de reconocimiento: {e}")
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
        
        return None

    def get_last_user_access(self, username):
        """Obtiene el último acceso de un usuario"""
        if not self.db_connection:
            return None
            
        try:
            cursor = self.db_connection.cursor(dictionary=True)
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

    def speak_last_access(self, username):
        """Lee en voz alta el último acceso del usuario"""
        access = self.get_last_user_access(username)
        
        if not access:
            message = f"No se encontraron accesos para el usuario {username}"
            print(f"❌ {message}")
        else:
            fecha = access['fecha_acceso']
            tipo = "permitido" if access['tipo_acceso'] == 'PERMITIDO' else "denegado"
            
            # Formatear fecha para lectura
            fecha_str = fecha.strftime('%d de %B a las %H:%M') if fecha else "fecha desconocida"
            
            message = f"El último acceso de {username} fue {tipo} el {fecha_str}"
            print(f"_____________________________________________________")
            print(f"📢 {message}")
            print(f"_____________________________________________________")
        
        # Leer en voz alta
        engine = self.setup_voice_engine()
        if engine:
            engine.say(message)
            engine.runAndWait()

    # Modificar el método search_user_access para usar voz
    def search_user_access(self, username=None):
        """Busca accesos de un usuario específico usando voz"""
        if not username:
            username = self.voice_search_user()
            
        if not username:
            return
            
        # Buscar coincidencias en la base de datos (búsqueda flexible)
        try:
            cursor = self.db_connection.cursor()
            cursor.execute("""
                SELECT nombre FROM usuarios 
                WHERE LOWER(nombre) LIKE %s
                ORDER BY nombre
            """, (f"%{username}%",))
            
            matches = cursor.fetchall()
            
            if not matches:
                print(f"❌ No se encontraron usuarios que coincidan con '{username}'")
                return
                
            if len(matches) == 1:
                # Un solo resultado, usar ese usuario
                selected_user = matches[0][0]
                print(f"✅ Usuario encontrado: {selected_user}")
            else:
                # Múltiples resultados, mostrar opciones
                print("\n🔍 Múltiples usuarios encontrados:")
                for i, (match,) in enumerate(matches, 1):
                    print(f"{i}. {match}")
                
                try:
                    selection = int(input("Seleccione el número del usuario: ")) - 1
                    if 0 <= selection < len(matches):
                        selected_user = matches[selection][0]
                    else:
                        print("❌ Selección inválida")
                        return
                except ValueError:
                    print("❌ Por favor ingrese un número válido")
                    return
            
            # Mostrar historial completo
            print(f"\n📋 HISTORIAL DE ACCESOS DE: {selected_user}")
            print("-" * 50)
            
            cursor.execute("""
                SELECT tipo_acceso, fecha_acceso, similitud
                FROM accesos 
                WHERE nombre_usuario = %s
                ORDER BY fecha_acceso DESC
            """, (selected_user,))
            
            resultados = cursor.fetchall()
            
            if resultados:
                for resultado in resultados:
                    similitud = resultado[2]
                    if hasattr(similitud, 'item'):
                        similitud = similitud.item()
                    print(f"{resultado[1]} | {resultado[0]} | Similitud: {similitud or 'N/A'}")
                
                # Leer el último acceso en voz alta
                self.speak_last_access(selected_user)
            else:
                print("No se encontraron accesos para este usuario")
                
        except Exception as e:
            print(f"❌ Error en búsqueda: {e}")

    def start_web_server(self):
        """Inicia un servidor web integrado para el panel de administración"""
        try:
            # Crear handler personalizado
            class WebHandler(http.server.BaseHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    self.db_config = {
                        'host': 'localhost',
                        'user': 'root',
                        'password': '123456798',
                        'database': 'facial_recognition_db'
                    }
                    super().__init__(*args)
                
                def do_GET(self):
                    if self.path == '/':
                        self.serve_index()
                    elif self.path == '/data':
                        self.send_data()
                    elif self.path == '/exportar':
                        self.export_data('accesos')
                    elif self.path == '/exportar-usuarios':
                        self.export_data('usuarios')
                    elif self.path == '/exportar-accesos':
                        self.export_data('accesos')
                    else:
                        self.send_error(404, "Página no encontrada")
                
                def do_POST(self):
                    if self.path == '/limpiar':
                        self.handle_clean()
                    else:
                        self.send_error(404, "Endpoint no encontrado")
                
                def serve_index(self):
                    """Sirve el archivo index.html"""
                    try:
                        with open('web_admin/index.html', 'rb') as f:
                            content = f.read()
                        
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html; charset=utf-8')
                        self.end_headers()
                        self.wfile.write(content)
                        
                    except FileNotFoundError:
                        self.send_error(404, "Archivo no encontrado")
                    except Exception as e:
                        self.send_error(500, f"Error: {str(e)}")
                
                def send_data(self):
                    """Envía datos JSON para el panel"""
                    try:
                        conn = mysql.connector.connect(**self.db_config)
                        cursor = conn.cursor(dictionary=True)
                        
                        # Obtener estadísticas
                        stats = {}
                        queries = {
                            'total_usuarios': "SELECT COUNT(*) as count FROM usuarios",
                            'total_accesos': "SELECT COUNT(*) as count FROM accesos",
                            'accesos_permitidos': "SELECT COUNT(*) as count FROM accesos WHERE tipo_acceso = 'PERMITIDO'",
                            'accesos_denegados': "SELECT COUNT(*) as count FROM accesos WHERE tipo_acceso = 'DENEGADO'"
                        }
                        
                        for key, query in queries.items():
                            cursor.execute(query)
                            stats[key] = cursor.fetchone()['count']
                        
                        # Obtener usuarios
                        cursor.execute("SELECT id, nombre, fecha_registro, ultimo_acceso, activo FROM usuarios ORDER BY nombre")
                        usuarios = cursor.fetchall()
                        
                        # Obtener últimos accesos
                        cursor.execute("""
                            SELECT id, nombre_usuario, tipo_acceso, fecha_acceso, similitud, usuario_id
                            FROM accesos 
                            ORDER BY fecha_acceso DESC 
                            LIMIT 20
                        """)
                        accesos = cursor.fetchall()
                        
                        conn.close()
                        
                        data = {
                            'stats': stats,
                            'usuarios': usuarios,
                            'accesos': accesos
                        }
                        
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json; charset=utf-8')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                        self.wfile.write(json.dumps(data, default=str).encode('utf-8'))
                        
                    except Exception as e:
                        self.send_error(500, f"Error obteniendo datos: {str(e)}")
                
                def export_data(self, tipo_exportacion):
                    """Exporta datos a CSV"""
                    try:
                        conn = mysql.connector.connect(**self.db_config)
                        cursor = conn.cursor()
                        
                        if tipo_exportacion == 'usuarios':
                            cursor.execute("SELECT id, nombre, fecha_registro, ultimo_acceso, activo FROM usuarios ORDER BY nombre")
                            datos = cursor.fetchall()
                            filename = 'export_usuarios.csv'
                            encabezados = ['ID', 'Nombre', 'Fecha Registro', 'Último Acceso', 'Activo']
                        else:
                            cursor.execute("""
                                SELECT id, nombre_usuario, tipo_acceso, fecha_acceso, similitud, usuario_id
                                FROM accesos ORDER BY fecha_acceso DESC
                            """)
                            datos = cursor.fetchall()
                            filename = 'export_accesos.csv'
                            encabezados = ['ID', 'Usuario', 'Tipo Acceso', 'Fecha Acceso', 'Similitud', 'ID Usuario']
                        
                        # Crear CSV en memoria
                        output = StringIO()
                        writer = csv.writer(output)
                        writer.writerow(encabezados)
                        
                        # Convertir todos los valores a string
                        for fila in datos:
                            fila_str = [str(valor) if valor is not None else '' for valor in fila]
                            writer.writerow(fila_str)
                        
                        csv_data = output.getvalue()
                        conn.close()
                        
                        # Enviar respuesta
                        self.send_response(200)
                        self.send_header('Content-type', 'text/csv; charset=utf-8')
                        self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                        self.send_header('Content-Length', str(len(csv_data.encode('utf-8'))))
                        self.end_headers()
                        
                        self.wfile.write(csv_data.encode('utf-8'))
                        
                    except Exception as e:
                        self.send_error(500, f"Error exportando datos: {str(e)}")
                
                def handle_clean(self):
                    """Maneja la limpieza de la base de datos"""
                    try:
                        content_length = int(self.headers['Content-Length'])
                        post_data = self.rfile.read(content_length).decode('utf-8')
                        data = parse_qs(post_data)
                        
                        tipo = data.get('tipo', [''])[0]
                        confirmacion = data.get('confirmacion', [''])[0]
                        
                        if confirmacion != '123456798':
                            self.send_response(400)
                            self.send_header('Content-type', 'text/plain; charset=utf-8')
                            self.end_headers()
                            self.wfile.write('Confirmación incorrecta'.encode('utf-8'))
                            return
                        
                        conn = mysql.connector.connect(**self.db_config)
                        cursor = conn.cursor()
                        
                        # Desactivar verificaciones de claves foráneas
                        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                        
                        if tipo == "accesos":
                            cursor.execute("TRUNCATE TABLE accesos")
                            mensaje = "Historial de accesos eliminado"
                        elif tipo == "todo":
                            cursor.execute("TRUNCATE TABLE accesos")
                            cursor.execute("TRUNCATE TABLE usuarios")
                            mensaje = "Todos los datos eliminados"
                        else:
                            raise ValueError("Tipo de limpieza no válido")
                        
                        # Reactivar verificaciones
                        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                        conn.commit()
                        conn.close()
                        
                        self.send_response(200)
                        self.send_header('Content-type', 'text/plain; charset=utf-8')
                        self.end_headers()
                        self.wfile.write(mensaje.encode('utf-8'))
                        
                    except Exception as e:
                        self.send_error(500, f"Error limpiando base de datos: {str(e)}")
            
            # Iniciar servidor en puerto 8000
            self.web_server = socketserver.TCPServer(("", 8000), WebHandler)
            print(f"🌐 Servidor web iniciado en http://localhost:8000")
            
            # Ejecutar servidor en segundo plano
            server_thread = threading.Thread(target=self.web_server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            
            return True
            
        except Exception as e:
            print(f"❌ Error iniciando servidor web: {e}")
            return False

    def open_web_admin(self):
        """Abre el panel web de administración"""
        try:
            # Crear carpeta web_admin si no existe
            if not os.path.exists('web_admin'):
                os.makedirs('web_admin')
                print("📁 Carpeta web_admin creada")
            
            # Crear archivo index.html si no existe
            if not os.path.exists('web_admin/index.html'):
                # HTML básico como fallback
                basic_html = """
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Panel Admin - Reconocimiento Facial</title>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                </head>
                <body>
                    <h1>Panel de Administración</h1>
                    <p>El archivo index.html no se encontró. Por favor, coloca tu HTML en web_admin/index.html</p>
                </body>
                </html>
                """
                with open('web_admin/index.html', 'w', encoding='utf-8') as f:
                    f.write(basic_html)
                print("📄 Archivo index.html básico creado")
            
            # Iniciar servidor web si no está iniciado
            if not self.web_server:
                if not self.start_web_server():
                    return
            
            # Abrir navegador
            web_url = "http://localhost:8000"
            print(f"🌐 Abriendo panel web: {web_url}")
            webbrowser.open(web_url)
            
            print("✅ Panel web abierto en el navegador")
            print("📋 Puedes administrar la base de datos desde allí")
            
        except Exception as e:
            print(f"❌ Error abriendo el panel web: {e}")

    def send_detailed_email(self, frame, username, access_type, similarity):
        """Envía correo con detalles completos"""
        try:
            # Configuración de email
            SENDER_EMAIL = "caquiamir@gmail.com"
            SENDER_PASSWORD = "yuph jrnv elrd qwmq"
            RECEIVER_EMAIL = "l9591667@gmail.com"
            
            if not SENDER_PASSWORD.strip():
                print("❌ No se ingresó contraseña")
                return
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_path = f"access_{timestamp}.jpg"
            
            cv2.imwrite(image_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
            
            history = self.get_access_history(5)
            
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = RECEIVER_EMAIL
            msg['Subject'] = f"🔐 {access_type} - Sistema Facial - {datetime.now().strftime('%d/%m %H:%M')}"
            
            history_table = ""
            for access in history:
                similitud = access['similitud']
                if hasattr(similitud, 'item'):
                    similitud = similitud.item()
                
                fecha = access['fecha_acceso']
                history_table += f"""
                <tr>
                    <td>{access['nombre_usuario'] or 'Desconocido'}</td>
                    <td>{access['tipo_acceso']}</td>
                    <td>{fecha.strftime('%d/%m %H:%M')}</td>
                    <td>{similitud if similitud is not None else 'N/A'}</td>
                </tr>
                """
            
            if hasattr(similarity, 'item'):
                similarity = similarity.item()
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                    .container {{ background: white; padding: 30px; border-radius: 15px; max-width: 600px; margin: 0 auto; }}
                    .header {{ background: {'#4CAF50' if access_type == 'PERMITIDO' else '#f44336'}; 
                              color: white; padding: 20px; border-radius: 10px; text-align: center; }}
                    .details {{ background: #f9f9f9; padding: 20px; border-radius: 10px; margin: 20px 0; }}
                    .detail-row {{ display: flex; justify-content: space-between; margin: 10px 0; padding: 5px; }}
                    .history {{ margin-top: 30px; }}
                    table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                    th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
                    th {{ background-color: #f2f2f2; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>{'✅ ACCESO PERMITIDO' if access_type == 'PERMITIDO' else '❌ ACCESO DENEGADO'}</h1>
                        <p>Sistema de Reconocimiento Facial</p>
                    </div>
                    
                    <div class="details">
                        <h3>📋 Detalles del Evento</h3>
                        <div class="detail-row">
                            <strong>👤 Usuario:</strong>
                            <span>{username}</span>
                        </div>
                        <div class="detail-row">
                            <strong>📅 Fecha y Hora:</strong>
                            <span>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
                        </div>
                        <div class="detail-row">
                            <strong>🔍 Nivel de Similitud:</strong>
                            <span>{float(similarity):.3f}</span>
                        </div>
                        <div class="detail-row">
                            <strong>🎯 Resultado:</strong>
                            <span style="color: {'green' if access_type == 'PERMITIDO' else 'red'}; 
                                        font-weight: bold;">
                                {access_type}
                            </span>
                        </div>
                    </div>
                    
                    <div class="history">
                        <h3>📊 Historial Reciente de Accesos</h3>
                        <table>
                            <tr>
                                <th>Usuario</th>
                                <th>Tipo</th>
                                <th>Fecha/Hora</th>
                                <th>Similitud</th>
                            </tr>
                            {history_table}
                        </table>
                    </div>
                </div>
            </body>
            </html>
            """
            
            msg.attach(MIMEText(html_content, 'html'))
            
            with open(image_path, 'rb') as f:
                img = MIMEImage(f.read(), name=f"acceso_{username}_{timestamp}.jpg")
            msg.attach(img)
            
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.send_message(msg)
            
            print("✅ Correo con reporte enviado")
            
            user_id = self.get_user_id(username) if access_type == 'PERMITIDO' else None
            
            if hasattr(similarity, 'item'):
                similarity_db = similarity.item()
            else:
                similarity_db = float(similarity)
                
            self.log_access(user_id, username, access_type, similarity_db, image_path)
            
            time.sleep(2)
            if os.path.exists(image_path):
                os.remove(image_path)
                
        except Exception as e:
            print(f"❌ Error enviando correo: {e}")

    def recognize_user(self):
        """Sistema principal de reconocimiento"""
        frame = self.capture_face()
        if frame is None:
            return
        
        current_features = self.extract_advanced_features(frame)
        
        if current_features is None:
            print("❌ No se detectó rostro")
            self.send_detailed_email(frame, "Desconocido", "DENEGADO", 0.0)
            return
        
        best_match = "Desconocido"
        best_similarity = 0.0
        
        for name, user_data in self.known_faces.items():
            similarity = self.compare_faces(current_features, user_data['features'])
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = name
        
        print(f"🔍 Similitud: {best_similarity:.3f}")
        
        if best_similarity > 0.6:
            print(f"🎉 ¡Acceso concedido a {best_match}!")
            self.send_detailed_email(frame, best_match, "PERMITIDO", best_similarity)
        else:
            print("❌ Acceso denegado")
            self.send_detailed_email(frame, "Desconocido", "DENEGADO", best_similarity)

    def run_system(self):
        """Sistema principal"""
        print("🤖 SISTEMA DE RECONOCIMIENTO FACIAL PARA LIMASECURITY")
        print("=" * 60)
        
        if not self.db_connection:
            print("❌ No se pudo conectar a MySQL")
            return
        
        while True:
            print("\n🎯 MENÚ PRINCIPAL")
            print("1. 🔐 Verificar acceso")
            print("2. 🌐 Abrir Panel Web de Administración")
            print("3. 🔍 Buscar accesos de usuario")
            print("4. 👥 Ver usuarios registrados")
            print("5. 📄 Exportar reporte a texto")
            print("6. 🚪 Salir")
            
            choice = input("Seleccione opción: ").strip()
            
            if choice == "1":
                self.recognize_user()
            elif choice == "2":
                self.open_web_admin()
            elif choice == "3":
                 self.search_user_access()      
            elif choice == "4":
                print("\n👥 USUARIOS REGISTRADOS:")
                if self.known_faces:
                    for user in self.known_faces.keys():
                        print(f"  👤 {user}")
                else:
                    print("  No hay usuarios registrados")
            elif choice == "5":
                self.export_to_text_file()
            elif choice == "6":
                print("👋 ¡Hasta pronto!")
                if self.db_connection:
                    self.db_connection.close()
                if self.web_server:
                    self.web_server.shutdown()
                break
            else:
                print("❌ Opción no válida")

# Ejecutar el sistema
if __name__ == "__main__":
    system = FacialRecognitionDB()
    system.run_system()

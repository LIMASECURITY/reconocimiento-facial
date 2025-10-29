import getpass
import threading
from clases.database import DatabaseManager
from clases.reconocimiento_fac import FacialRecognition
from clases.email_envio import EmailSender
from clases.voice import VoiceHandler
from clases.web_server import WebServerManager
from clases.auth_system import AuthSystem
import config

class FacialRecognitionSystem:
    def __init__(self):
        print("🤖 INICIANDO SISTEMA DE RECONOCIMIENTO FACIAL")
        print("=" * 60)
        
        # Inicializar componentes
        self.db = DatabaseManager()
        self.face_recognition = FacialRecognition(self.db)
        self.email_sender = EmailSender(self.db)
        self.voice_handler = VoiceHandler()
        self.web_server = WebServerManager(self.db)
        # Pasar email_sender al AuthSystem
        self.auth_system = AuthSystem(self.db, self.face_recognition, self.email_sender)
        
        # Verificar e inicializar base de datos
        if self.db.test_connection():
            # Solo llamar a create_tables() una vez - esto incluye create_user_table()
            self.db.create_tables()
        else:
            print("❌ No se pudo establecer conexión con la base de datos.")
    
    def run_system(self):
        """Sistema principal con autenticación por roles"""
        try:
            while True:
                print("\n🤖 SISTEMA DE RECONOCIMIENTO FACIAL")
                print("=" * 50)
                print("1. 🔐 Iniciar sesión")
                print("2. 🚪 Salir del sistema")
                
                try:
                    choice = input("Seleccione opción: ").strip()
                    
                    if choice == "1":
                        if self.auth_system.login():
                            # El manejo de usuarios autenticados ahora se hace dentro de AuthSystem
                            # Solo los administradores necesitan manejo especial
                            if self.auth_system.current_role == 'admin':
                                self.handle_admin_session()
                        else:
                            continue
                    elif choice == "2":
                        print("👋 ¡Hasta pronto!")
                        if self.web_server.web_server:
                            self.web_server.web_server.shutdown()
                        break
                    else:
                        print("❌ Opción no válida")
                        
                except KeyboardInterrupt:
                    print("\n🛑 Interrupción por usuario")
                    break
                except Exception as e:
                    print(f"❌ Error en menú: {e}")
                    
        finally:
            print("✅ Sistema cerrado correctamente")
    
    def handle_admin_session(self):
        """Maneja la sesión de administrador - VERSIÓN SIMPLIFICADA"""
        while True:
            action = self.auth_system.show_admin_menu()
            
            if action == 'admin_panel':
                self.open_admin_panel()
            elif action == 'view_users':
                self.show_all_users()
            elif action == 'voice_search':
                self.voice_search_access()
            elif action == 'logout':
                break
            else:
                continue

    def open_admin_panel(self):
        """Abre el panel de administración web"""
        print("🌐 Abriendo Panel Web de Administración...")
        if self.web_server.open_web_admin():
            print("📋 Panel web funcionando en segundo plano")
        else:
            print("❌ Error al abrir panel web")
    
    def show_all_users(self):
        """Muestra todos los usuarios registrados"""
        print("\n👥 USUARIOS REGISTRADOS EN EL SISTEMA")
        print("=" * 50)
        
        users = self.db.get_all_users()
        
        if not users:
            print("No hay usuarios registrados en el sistema")
            return
        
        print(f"{'USUARIO':<20} {'REGISTRO':<12} {'ÚLTIMO ACCESO':<15} {'ROL':<8} {'ESTADO':<8}")
        print("-" * 70)
        
        for user in users:
            estado = "🟢 Activo" if user['activo'] else "🔴 Inactivo"
            fecha_reg = user['fecha_registro'].strftime('%d/%m/%Y') if user['fecha_registro'] else 'N/A'
            fecha_acceso = user['ultimo_acceso'].strftime('%d/%m/%Y') if user['ultimo_acceso'] else 'Nunca'
            
            print(f"{user['nombre']:<20} {fecha_reg:<12} {fecha_acceso:<15} {user['rol']:<8} {estado:<8}")
    
    def voice_search_access(self):
        """Búsqueda de accesos por voz para administradores"""
        print("\n🔍 BÚSQUEDA DE ACCESOS POR VOZ")
        username = self.voice_handler.voice_search_user()
        
        if username:
            # Usar el método de búsqueda del auth_system
            self.auth_system._process_user_search(username)
        else:
            print("❌ No se pudo reconocer el nombre del usuario")
    
    def show_complete_stats(self):
        """Muestra estadísticas completas del sistema"""
        print("\n📊 ESTADÍSTICAS COMPLETAS DEL SISTEMA")
        print("=" * 50)
        
        conn = self.db.get_connection()
        if not conn:
            print("❌ No se pudo conectar a la base de datos")
            return
            
        try:
            cursor = conn.cursor()
            
            # Estadísticas generales
            cursor.execute("SELECT COUNT(*) FROM usuarios")
            total_usuarios = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM accesos")
            total_accesos = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM accesos WHERE tipo_acceso = 'PERMITIDO'")
            accesos_permitidos = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM accesos WHERE tipo_acceso = 'DENEGADO'")
            accesos_denegados = cursor.fetchone()[0]
            
            # Usuario con más accesos
            cursor.execute("""
                SELECT u.nombre, COUNT(a.id) as total_accesos
                FROM usuarios u
                JOIN accesos a ON u.id = a.usuario_id
                GROUP BY u.id, u.nombre
                ORDER BY total_accesos DESC
                LIMIT 1
            """)
            usuario_top = cursor.fetchone()
            
            # Acceso más reciente
            cursor.execute("""
                SELECT nombre_usuario, tipo_acceso, fecha_acceso
                FROM accesos
                ORDER BY fecha_acceso DESC
                LIMIT 1
            """)
            acceso_reciente = cursor.fetchone()
            
            print(f"👥 Total de usuarios: {total_usuarios}")
            print(f"📊 Total de accesos: {total_accesos}")
            print(f"✅ Accesos permitidos: {accesos_permitidos}")
            print(f"❌ Accesos denegados: {accesos_denegados}")
            
            if total_accesos > 0:
                porcentaje_exito = (accesos_permitidos / total_accesos) * 100
                print(f"🎯 Tasa de éxito: {porcentaje_exito:.1f}%")
            
            if usuario_top:
                print(f"🏆 Usuario más activo: {usuario_top[0]} ({usuario_top[1]} accesos)")
            
            if acceso_reciente:
                fecha = acceso_reciente[2].strftime('%d/%m/%Y %H:%M') if acceso_reciente[2] else 'N/A'
                print(f"🕒 Acceso más reciente: {acceso_reciente[0]} - {acceso_reciente[1]} - {fecha}")
                
        except Exception as e:
            print(f"❌ Error obteniendo estadísticas: {e}")
        finally:
            if conn and conn.is_connected():
                conn.close()

if __name__ == "__main__":
    system = FacialRecognitionSystem()
    system.run_system()
import http.server
import socketserver
import json
import csv
import threading
import webbrowser
import os
from urllib.parse import parse_qs
from io import StringIO
import mysql.connector
from mysql.connector import Error
import config

class WebServerManager:
    def __init__(self, database_manager):
        self.db = database_manager
        self.web_server = None
    
    def start_web_server(self):
        """Inicia un servidor web integrado para el panel de administración"""
        try:
            # Crear handler personalizado
            class WebHandler(http.server.BaseHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    self.db_config = config.DB_CONFIG
                    super().__init__(*args)
                
                def log_message(self, format, *args):
                    """Silencia los logs del servidor para evitar spam"""
                    return
                
                def create_connection(self):
                    """Crea una nueva conexión independiente a la base de datos"""
                    try:
                        conn = mysql.connector.connect(**self.db_config)
                        return conn
                    except Error as e:
                        print(f"❌ Error creando conexión web: {e}")
                        return None
                def serve_user_history(self):
                    """Sirve una página de historial personalizado para usuarios"""
                    # Obtener parámetros de la URL
                    from urllib.parse import urlparse, parse_qs
                    parsed = urlparse(self.path)
                    query_params = parse_qs(parsed.query)
                    
                    username = query_params.get('user', [None])[0]
                    
                    if not username:
                        self.send_error(400, "Falta parámetro de usuario")
                        return
                    
                    conn = self.create_connection()
                    if not conn:
                        self.send_error(500, "No se pudo conectar a la base de datos")
                        return
                        
                    try:
                        cursor = conn.cursor()
                        
                        # Obtener historial del usuario
                        cursor.execute("""
                            SELECT tipo_acceso, fecha_acceso, similitud
                            FROM accesos 
                            WHERE nombre_usuario = %s
                            ORDER BY fecha_acceso DESC
                            LIMIT 50
                        """, (username,))
                        
                        historial = cursor.fetchall()
                        
                        # Crear HTML personalizado
                        html_content = f"""
                        <!DOCTYPE html>
                        <html>
                        <head>
                            <meta charset="UTF-8">
                            <title>Historial de {username}</title>
                            <style>
                                body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
                                .container {{ background: white; padding: 30px; border-radius: 15px; max-width: 1000px; margin: 0 auto; }}
                                .header {{ background: #3498db; color: white; padding: 20px; border-radius: 10px; text-align: center; }}
                                table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
                                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                                th {{ background-color: #34495e; color: white; }}
                                .permitido {{ color: #27ae60; font-weight: bold; }}
                                .denegado {{ color: #e74c3c; font-weight: bold; }}
                                .stats {{ background: #f8f9fa; padding: 15px; border-radius: 10px; margin: 20px 0; }}
                            </style>
                        </head>
                        <body>
                            <div class="container">
                                <div class="header">
                                    <h1>📋 Historial de Accesos</h1>
                                    <h2>👤 Usuario: {username}</h2>
                                </div>
                        """
                        
                        if historial:
                            # Calcular estadísticas
                            total = len(historial)
                            permitidos = sum(1 for acceso in historial if acceso[0] == 'PERMITIDO')
                            porcentaje = (permitidos / total * 100) if total > 0 else 0
                            
                            html_content += f"""
                                <div class="stats">
                                    <h3>📊 Estadísticas</h3>
                                    <p>Total de accesos: {total}</p>
                                    <p>Accesos permitidos: {permitidos}</p>
                                    <p>Accesos denegados: {total - permitidos}</p>
                                    <p>Porcentaje de éxito: {porcentaje:.1f}%</p>
                                </div>
                                
                                <table>
                                    <tr>
                                        <th>Fecha/Hora</th>
                                        <th>Tipo de Acceso</th>
                                        <th>Nivel de Similitud</th>
                                    </tr>
                            """
                            
                            for acceso in historial:
                                tipo_clase = 'permitido' if acceso[0] == 'PERMITIDO' else 'denegado'
                                fecha = acceso[1].strftime('%d/%m/%Y %H:%M:%S') if acceso[1] else 'N/A'
                                similitud = f"{(acceso[2] * 100):.1f}%" if acceso[2] else 'N/A'
                                
                                html_content += f"""
                                    <tr>
                                        <td>{fecha}</td>
                                        <td class="{tipo_clase}">{acceso[0]}</td>
                                        <td>{similitud}</td>
                                    </tr>
                                """
                            
                            html_content += "</table>"
                        else:
                            html_content += "<p>No se encontraron accesos para este usuario.</p>"
                        
                        html_content += """
                            </div>
                        </body>
                        </html>
                        """
                        
                        self.send_response(200)
                        self.send_header('Content-type', 'text/html; charset=utf-8')
                        self.send_header('Content-Length', str(len(html_content)))
                        self.end_headers()
                        self.wfile.write(html_content.encode('utf-8'))
                        
                    except Exception as e:
                        self.send_error(500, f"Error generando historial: {str(e)}")
                    finally:
                        if conn and conn.is_connected():
                            conn.close()
                def do_GET(self):
                    try:
                        if self.path == '/':
                            self.serve_index()
                        elif self.path == '/data':
                            self.send_data()
                        elif self.path == '/exportar-usuarios':
                            self.export_data('usuarios')
                        elif self.path == '/exportar-accesos':
                            self.export_data('accesos')
                        elif self.path.startswith('/historial-usuario'):
                            self.serve_user_history()
                        else:
                            self.send_error(404, "Página no encontrada")
                    except Exception as e:
                        print(f"❌ Error en GET {self.path}: {e}")
                        self.send_error(500, f"Error interno: {str(e)}")
                
                def do_POST(self):
                    try:
                        if self.path == '/limpiar':
                            self.handle_clean()
                        else:
                            self.send_error(404, "Endpoint no encontrado")
                    except Exception as e:
                        print(f"❌ Error en POST {self.path}: {e}")
                        self.send_error(500, f"Error interno: {str(e)}")
                
                def serve_index(self):
                    """Sirve el archivo index.html"""
                    try:
                        # Cambiar al directorio web_admin para servir archivos estáticos
                        import os
                        original_dir = os.getcwd()
                        web_admin_dir = os.path.join(original_dir, 'web_admin')
                        
                        if os.path.exists(web_admin_dir):
                            os.chdir(web_admin_dir)
                        
                        try:
                            with open('index.html', 'rb') as f:
                                content = f.read()
                            
                            self.send_response(200)
                            self.send_header('Content-type', 'text/html; charset=utf-8')
                            self.send_header('Content-Length', str(len(content)))
                            self.end_headers()
                            self.wfile.write(content)
                        finally:
                            # Volver al directorio original
                            os.chdir(original_dir)
                            
                    except FileNotFoundError:
                        # Si no existe index.html, servir uno básico
                        self.serve_basic_index()
                    except Exception as e:
                        self.send_error(500, f"Error sirviendo índice: {str(e)}")
                
                def serve_basic_index(self):
                    """Sirve un index.html básico si no existe el archivo"""
                    basic_html = """
                    <!DOCTYPE html>
                    <html lang="es">
                    <head>
                        <meta charset="UTF-8">
                        <meta name="viewport" content="width=device-width, initial-scale=1.0">
                        <title>Panel Admin</title>
                        <style>
                            * {
                                margin: 0;
                                padding: 0;
                                box-sizing: border-box;
                            }

                            body {
                                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                min-height: 100vh;
                                padding: 20px;
                            }

                            .container {
                                max-width: 1200px;
                                margin: 0 auto;
                                background: white;
                                border-radius: 15px;
                                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                                overflow: hidden;
                            }

                            .header {
                                background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
                                color: white;
                                padding: 30px;
                                text-align: center;
                            }

                            .header h1 {
                                font-size: 2.5em;
                                margin-bottom: 10px;
                            }

                            .stats {
                                display: grid;
                                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                                gap: 20px;
                                padding: 30px;
                                background: #f8f9fa;
                            }

                            .stat-card {
                                background: white;
                                padding: 25px;
                                border-radius: 10px;
                                text-align: center;
                                box-shadow: 0 4px 15px rgba(0,0,0,0.1);
                            }

                            .stat-number {
                                font-size: 3em;
                                font-weight: bold;
                                color: #4CAF50;
                                margin-bottom: 10px;
                            }

                            .actions {
                                padding: 30px;
                                text-align: center;
                            }

                            .btn {
                                display: inline-block;
                                padding: 15px 30px;
                                margin: 10px;
                                border: none;
                                border-radius: 8px;
                                font-size: 1.1em;
                                font-weight: bold;
                                cursor: pointer;
                                text-decoration: none;
                                transition: transform 0.2s, box-shadow 0.2s;
                            }

                            .btn:hover {
                                transform: translateY(-2px);
                                box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                            }

                            .btn-primary {
                                background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
                                color: white;
                            }

                            .btn-danger {
                                background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
                                color: white;
                            }

                            .btn-warning {
                                background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%);
                                color: white;
                            }

                            .data-section {
                                padding: 30px;
                            }

                            .table-container {
                                overflow-x: auto;
                                margin: 20px 0;
                            }

                            table {
                                width: 100%;
                                border-collapse: collapse;
                                margin: 20px 0;
                            }

                            th, td {
                                padding: 12px;
                                text-align: left;
                                border-bottom: 1px solid #ddd;
                            }

                            th {
                                background-color: #4CAF50;
                                color: white;
                                font-weight: bold;
                            }

                            tr:hover {
                                background-color: #f5f5f5;
                            }

                            .dialog {
                                position: fixed;
                                top: 0;
                                left: 0;
                                width: 100%;
                                height: 100%;
                                background: rgba(0,0,0,0.5);
                                display: none;
                                justify-content: center;
                                align-items: center;
                                z-index: 1000;
                            }

                            .dialog-content {
                                background: white;
                                padding: 30px;
                                border-radius: 15px;
                                max-width: 500px;
                                width: 90%;
                            }

                            .dialog-options {
                                margin: 20px 0;
                            }

                            .dialog-options label {
                                display: block;
                                margin: 10px 0;
                                padding: 15px;
                                background: #f9f9f9;
                                border-radius: 8px;
                                border-left: 4px solid #4CAF50;
                            }

                            .dialog-confirm {
                                margin: 20px 0;
                                padding: 15px;
                                background: #fff3cd;
                                border-radius: 8px;
                                border-left: 4px solid #ff9800;
                            }

                            .dialog-confirm input {
                                width: 100%;
                                padding: 12px;
                                margin: 10px 0;
                                border: 2px solid #ddd;
                                border-radius: 5px;
                                font-size: 16px;
                            }

                            .dialog-buttons {
                                text-align: center;
                                margin-top: 20px;
                            }

                            .alert {
                                padding: 15px;
                                margin: 20px 0;
                                border-radius: 5px;
                                font-weight: bold;
                            }

                            .alert-success {
                                background-color: #d4edda;
                                color: #155724;
                                border: 1px solid #c3e6cb;
                            }

                            .alert-error {
                                background-color: #f8d7da;
                                color: #721c24;
                                border: 1px solid #f5c6cb;
                            }

                            .loading {
                                text-align: center;
                                padding: 20px;
                                color: #666;
                                font-style: italic;
                            }

                            @media (max-width: 768px) {
                                .stats {
                                    grid-template-columns: 1fr;
                                }
                                
                                .btn {
                                    display: block;
                                    margin: 10px auto;
                                    width: 90%;
                                }
                                
                                .table-container {
                                    overflow-x: auto;
                                }
                            }
                        </style>
                    </head>
                    <body>
                        <div class="container">
                            <div class="header">
                                <h1>🤖 Panel de Administración</h1>
                                <p>Sistema de Reconocimiento Facial - Servidor Integrado</p>
                            </div>

                            <div id="alert-container"></div>

                            <div class="stats" id="stats">
                                <div class="stat-card">
                                    <div class="stat-number" id="total-usuarios">0</div>
                                    <div class="stat-label">👥 Usuarios Registrados</div>
                                </div>
                                <div class="stat-card">
                                    <div class="stat-number" id="total-accesos">0</div>
                                    <div class="stat-label">📊 Total de Accesos</div>
                                </div>
                                <div class="stat-card">
                                    <div class="stat-number" id="accesos-permitidos">0</div>
                                    <div class="stat-label">✅ Accesos Permitidos</div>
                                </div>
                                <div class="stat-card">
                                    <div class="stat-number" id="accesos-denegados">0</div>
                                    <div class="stat-label">❌ Accesos Denegados</div>
                                </div>
                            </div>

                            <div class="actions">
                                <button class="btn btn-primary" onclick="exportData('usuarios')">💾 Exportar Usuarios</button>
                                <button class="btn btn-primary" onclick="exportData('accesos')">📊 Exportar Accesos</button>
                                <button class="btn btn-danger" onclick="showCleanDialog()">🗑️ Limpiar Base de Datos</button>
                                <button class="btn btn-warning" onclick="refreshData()">🔄 Actualizar Datos</button>
                            </div>

                            <div class="data-section">
                                <h2>👥 Usuarios Registrados</h2>
                                <div class="table-container">
                                    <table id="usuarios-table">
                                        <thead>
                                            <tr>
                                                <th>ID</th>
                                                <th>Nombre</th>
                                                <th>Fecha Registro</th>
                                                <th>Último Acceso</th>
                                                <th>Estado</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr>
                                                <td colspan="5" style="text-align: center;" class="loading">Cargando datos...</td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>

                                <h2>⏰ Últimos 20 Accesos</h2>
                                <div class="table-container">
                                    <table id="accesos-table">
                                        <thead>
                                            <tr>
                                                <th>Fecha/Hora</th>
                                                <th>Usuario</th>
                                                <th>Tipo</th>
                                                <th>Similitud</th>
                                                <th>ID Usuario</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            <tr>
                                                <td colspan="5" style="text-align: center;" class="loading">Cargando datos...</td>
                                            </tr>
                                        </tbody>
                                    </table>
                                </div>
                            </div>

                            <!-- Diálogo de limpieza -->
                            <div id="clean-dialog" class="dialog">
                                <div class="dialog-content">
                                    <h3>🗑️ Limpiar Base de Datos</h3>
                                    
                                    <div class="dialog-options">
                                        <label>
                                            <input type="radio" name="clean-type" value="accesos" checked>
                                            <strong>📋 Solo historial de accesos</strong><br>
                                            <small>Elimina todos los registros de accesos pero mantiene los usuarios</small>
                                        </label>
                                        <label>
                                            <input type="radio" name="clean-type" value="todo">
                                            <strong>🔥 Todos los datos (usuarios + accesos)</strong><br>
                                            <small>Elimina completamente toda la información del sistema</small>
                                        </label>
                                    </div>

                                    <div class="dialog-confirm">
                                        <p>⚠️ <strong>ACCIÓN IRREVERSIBLE</strong></p>
                                        <p>Ingrese la contraseña de confirmación:</p>
                                        <input type="password" id="confirm-input" placeholder="Escriba la contraseña aquí">
                                    </div>

                                    <div class="dialog-buttons">
                                        <button class="btn btn-danger" onclick="cleanData()" style="margin-right: 10px;">
                                            🗑️ EJECUTAR LIMPIEZA
                                        </button>
                                        <button class="btn" onclick="hideCleanDialog()" style="background: #6c757d; color: white;">
                                            ✖️ Cancelar
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <script>
                            // Mostrar alerta
                            function showAlert(message, type) {
                                const alertContainer = document.getElementById('alert-container');
                                alertContainer.innerHTML = `
                                    <div class="alert alert-${type}">
                                        ${message}
                                    </div>
                                `;
                                setTimeout(() => {
                                    alertContainer.innerHTML = '';
                                }, 5000);
                            }

                            // Cargar datos al iniciar
                            document.addEventListener('DOMContentLoaded', refreshData);

                            async function refreshData() {
                                try {
                                    showAlert('🔄 Cargando datos...', 'success');
                                    
                                    const response = await fetch('/data');
                                    if (!response.ok) {
                                        throw new Error(`Error ${response.status}: ${response.statusText}`);
                                    }
                                    
                                    const data = await response.json();
                                    
                                    // Actualizar estadísticas
                                    document.getElementById('total-usuarios').textContent = data.stats.total_usuarios;
                                    document.getElementById('total-accesos').textContent = data.stats.total_accesos;
                                    document.getElementById('accesos-permitidos').textContent = data.stats.accesos_permitidos;
                                    document.getElementById('accesos-denegados').textContent = data.stats.accesos_denegados;
                                    
                                    // Actualizar tabla de usuarios
                                    const usuariosTable = document.querySelector('#usuarios-table tbody');
                                    if (!data.usuarios || data.usuarios.length === 0) {
                                        usuariosTable.innerHTML = '<tr><td colspan="5" style="text-align: center;">No hay usuarios registrados</td></tr>';
                                    } else {
                                        usuariosTable.innerHTML = '';
                                        data.usuarios.forEach(user => {
                                            const fechaRegistro = user.fecha_registro ? 
                                                new Date(user.fecha_registro).toLocaleString('es-ES') : 'N/A';
                                            const ultimoAcceso = user.ultimo_acceso ? 
                                                new Date(user.ultimo_acceso).toLocaleString('es-ES') : 'Nunca';
                                            
                                            usuariosTable.innerHTML += `
                                                <tr>
                                                    <td>${user.id}</td>
                                                    <td><strong>${user.nombre}</strong></td>
                                                    <td>${fechaRegistro}</td>
                                                    <td>${ultimoAcceso}</td>
                                                    <td>${user.activo ? '✅ Activo' : '❌ Inactivo'}</td>
                                                </tr>
                                            `;
                                        });
                                    }
                                    
                                    // Actualizar tabla de accesos
                                    const accesosTable = document.querySelector('#accesos-table tbody');
                                    if (!data.accesos || data.accesos.length === 0) {
                                        accesosTable.innerHTML = '<tr><td colspan="5" style="text-align: center;">No hay registros de acceso</td></tr>';
                                    } else {
                                        accesosTable.innerHTML = '';
                                        data.accesos.forEach(acceso => {
                                            const fechaAcceso = acceso.fecha_acceso ? 
                                                new Date(acceso.fecha_acceso).toLocaleString('es-ES') : 'N/A';
                                            const similitud = acceso.similitud ? 
                                                parseFloat(acceso.similitud).toFixed(3) : 'N/A';
                                            
                                            accesosTable.innerHTML += `
                                                <tr>
                                                    <td>${fechaAcceso}</td>
                                                    <td><strong>${acceso.nombre_usuario}</strong></td>
                                                    <td>
                                                        <span style="color: ${acceso.tipo_acceso === 'PERMITIDO' ? 'green' : 'red'}; 
                                                                    font-weight: bold; padding: 4px 8px; border-radius: 4px;
                                                                    background: ${acceso.tipo_acceso === 'PERMITIDO' ? '#d4edda' : '#f8d7da'}">
                                                            ${acceso.tipo_acceso}
                                                        </span>
                                                    </td>
                                                    <td>${similitud}</td>
                                                    <td>${acceso.usuario_id || 'N/A'}</td>
                                                </tr>
                                            `;
                                        });
                                    }
                                    
                                    showAlert('✅ Datos actualizados correctamente', 'success');
                                    
                                } catch (error) {
                                    showAlert('❌ Error cargando datos: ' + error.message, 'error');
                                    console.error('Error:', error);
                                }
                            }

                            function exportData(tipo) {
                                const url = tipo === 'usuarios' ? '/exportar-usuarios' : '/exportar-accesos';
                                window.open(url, '_blank');
                                showAlert(`📥 Exportando ${tipo === 'usuarios' ? 'usuarios' : 'accesos'}...`, 'success');
                            }

                            function showCleanDialog() {
                                document.getElementById('clean-dialog').style.display = 'flex';
                                document.getElementById('confirm-input').value = '';
                            }

                            function hideCleanDialog() {
                                document.getElementById('clean-dialog').style.display = 'none';
                            }

                            async function cleanData() {
                                const tipo = document.querySelector('input[name="clean-type"]:checked').value;
                                const confirmacion = document.getElementById('confirm-input').value;
                                
                                if (confirmacion !== '123456798') {
                                    showAlert('❌ Contraseña incorrecta', 'error');
                                    return;
                                }
                                
                                if (!confirm(`⚠️ ¿ESTÁS ABSOLUTAMENTE SEGURO?\n\nEsta acción ${tipo === 'todo' ? 'eliminará TODOS los datos (usuarios y accesos)' : 'eliminará el historial de accesos'}.\n\nEsta acción NO se puede deshacer.`)) {
                                    return;
                                }
                                
                                try {
                                    showAlert('🔄 Procesando limpieza...', 'success');
                                    
                                    const formData = new URLSearchParams();
                                    formData.append('tipo', tipo);
                                    formData.append('confirmacion', confirmacion);
                                    
                                    const response = await fetch('/limpiar', {
                                        method: 'POST',
                                        headers: {
                                            'Content-Type': 'application/x-www-form-urlencoded',
                                        },
                                        body: formData
                                    });
                                    
                                    const result = await response.text();
                                    
                                    if (response.ok) {
                                        showAlert('✅ ' + result, 'success');
                                        refreshData();
                                        hideCleanDialog();
                                    } else {
                                        throw new Error(result);
                                    }
                                } catch (error) {
                                    showAlert('❌ Error limpiando base de datos: ' + error.message, 'error');
                                    console.error('Error:', error);
                                }
                            }

                            // Actualizar automáticamente cada 30 segundos
                            setInterval(refreshData, 30000);

                            // Cerrar diálogo haciendo clic fuera
                            document.getElementById('clean-dialog').addEventListener('click', function(e) {
                                if (e.target === this) {
                                    hideCleanDialog();
                                }
                            });

                            // Permitir cerrar con ESC
                            document.addEventListener('keydown', function(e) {
                                if (e.key === 'Escape') {
                                    hideCleanDialog();
                                }
                            });
                        </script>
                    </body>
                    </html>
                    """
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.send_header('Content-Length', str(len(basic_html)))
                    self.end_headers()
                    self.wfile.write(basic_html.encode('utf-8'))
                
                def send_data(self):
                    """Envía datos JSON para el panel"""
                    conn = self.create_connection()
                    if not conn:
                        self.send_error(500, "No se pudo conectar a la base de datos")
                        return
                        
                    try:
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
                        
                        data = {
                            'stats': stats,
                            'usuarios': usuarios,
                            'accesos': accesos
                        }
                        
                        response_data = json.dumps(data, default=str, ensure_ascii=False).encode('utf-8')
                        
                        self.send_response(200)
                        self.send_header('Content-type', 'application/json; charset=utf-8')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.send_header('Content-Length', str(len(response_data)))
                        self.end_headers()
                        self.wfile.write(response_data)
                        
                    except Exception as e:
                        print(f"❌ Error enviando datos: {e}")
                        self.send_error(500, f"Error obteniendo datos: {str(e)}")
                    finally:
                        if conn and conn.is_connected():
                            conn.close()
                
                def export_personal_history(self):
                    """Exporta el historial personal a CSV"""
                    try:
                        from urllib.parse import urlparse, parse_qs
                        parsed = urlparse(self.path)
                        query_params = parse_qs(parsed.query)
                        
                        username = query_params.get('user', [None])[0]
                        
                        if not username:
                            self.send_error(400, "Falta parámetro de usuario")
                            return
                        
                        conn = self.create_connection()
                        if not conn:
                            self.send_error(500, "No se pudo conectar a la base de datos")
                            return
                            
                        try:
                            cursor = conn.cursor()
                            
                            cursor.execute("""
                                SELECT fecha_acceso, tipo_acceso, similitud, imagen_path
                                FROM accesos 
                                WHERE nombre_usuario = %s
                                ORDER BY fecha_acceso DESC
                            """, (username,))
                            
                            datos = cursor.fetchall()
                            
                            # Crear CSV en memoria
                            output = StringIO()
                            writer = csv.writer(output)
                            writer.writerow(['Fecha Acceso', 'Tipo Acceso', 'Similitud', 'Ruta Imagen'])
                            
                            for fila in datos:
                                fecha = fila[0].strftime('%Y-%m-%d %H:%M:%S') if fila[0] else ''
                                tipo = fila[1] or ''
                                similitud = f"{(fila[2] * 100):.2f}%" if fila[2] is not None else 'N/A'
                                imagen = fila[3] or ''
                                
                                writer.writerow([fecha, tipo, similitud, imagen])
                            
                            csv_data = output.getvalue().encode('utf-8')
                            
                            # Enviar respuesta
                            self.send_response(200)
                            self.send_header('Content-type', 'text/csv; charset=utf-8')
                            self.send_header('Content-Disposition', f'attachment; filename="historial_{username}.csv"')
                            self.send_header('Content-Length', str(len(csv_data)))
                            self.end_headers()
                            
                            self.wfile.write(csv_data)
                            print(f"✅ Historial personal de {username} exportado a CSV")
                            
                        except Exception as e:
                            print(f"❌ Error exportando historial personal: {e}")
                            self.send_error(500, f"Error exportando datos: {str(e)}")
                        finally:
                            if conn and conn.is_connected():
                                conn.close()
                                
                    except Exception as e:
                        self.send_error(500, f"Error interno: {str(e)}")

                def export_data(self, tipo_exportacion):
                    """Exporta datos a CSV"""
                    conn = self.create_connection()
                    if not conn:
                        self.send_error(500, "No se pudo conectar a la base de datos")
                        return
                        
                    try:
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
                        
                        csv_data = output.getvalue().encode('utf-8')
                        
                        # Enviar respuesta
                        self.send_response(200)
                        self.send_header('Content-type', 'text/csv; charset=utf-8')
                        self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                        self.send_header('Content-Length', str(len(csv_data)))
                        self.end_headers()
                        
                        self.wfile.write(csv_data)
                        
                    except Exception as e:
                        print(f"❌ Error exportando datos: {e}")
                        self.send_error(500, f"Error exportando datos: {str(e)}")
                    finally:
                        if conn and conn.is_connected():
                            conn.close()
                
                def handle_clean(self):
                    """Maneja la limpieza de la base de datos"""
                    conn = self.create_connection()
                    if not conn:
                        self.send_error(500, "No se pudo conectar a la base de datos")
                        return
                        
                    try:
                        content_length = int(self.headers['Content-Length'])
                        post_data = self.rfile.read(content_length).decode('utf-8')
                        data = parse_qs(post_data)
                        
                        tipo = data.get('tipo', [''])[0]
                        confirmacion = data.get('confirmacion', [''])[0]
                        
                        if confirmacion != config.SYSTEM_CONFIG['admin_password']:
                            self.send_response(400)
                            self.send_header('Content-type', 'text/plain; charset=utf-8')
                            self.end_headers()
                            self.wfile.write('Confirmación incorrecta'.encode('utf-8'))
                            return
                        
                        cursor = conn.cursor()
                        
                        # Desactivar verificaciones de claves foráneas
                        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                        
                        if tipo == "accesos":
                            cursor.execute("TRUNCATE TABLE accesos")
                            mensaje = "Historial de accesos eliminado correctamente"
                        elif tipo == "todo":
                            cursor.execute("TRUNCATE TABLE accesos")
                            cursor.execute("TRUNCATE TABLE usuarios")
                            mensaje = "Todos los datos eliminados correctamente"
                        else:
                            raise ValueError("Tipo de limpieza no válido")
                        
                        # Reactivar verificaciones
                        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
                        conn.commit()
                        
                        self.send_response(200)
                        self.send_header('Content-type', 'text/plain; charset=utf-8')
                        self.end_headers()
                        self.wfile.write(mensaje.encode('utf-8'))
                        
                        print(f"✅ Limpieza ejecutada via web: {tipo}")
                        
                    except Exception as e:
                        print(f"❌ Error en limpieza web: {e}")
                        self.send_error(500, f"Error limpiando base de datos: {str(e)}")
                    finally:
                        if conn and conn.is_connected():
                            conn.close()
            
            # Configurar el servidor para reutilizar direcciones
            socketserver.TCPServer.allow_reuse_address = True
            
            # Iniciar servidor en puerto configurado
            port = config.SYSTEM_CONFIG['web_server_port']
            self.web_server = socketserver.TCPServer(("", port), WebHandler)
            print(f"🌐 Servidor web iniciado en http://localhost:{port}")
            print("✅ El servidor web ahora usa conexiones independientes a MySQL")
            
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
            
            # Verificar si el archivo index.html existe, si no se usará el básico
            index_path = os.path.join('web_admin', 'index.html')
            if not os.path.exists(index_path):
                print("ℹ️  No se encontró index.html personalizado, usando versión básica")
            
            # Iniciar servidor web si no está iniciado
            if not self.web_server:
                if not self.start_web_server():
                    return False
            
            # Abrir navegador
            port = config.SYSTEM_CONFIG['web_server_port']
            web_url = f"http://localhost:{port}"
            print(f"🌐 Abriendo panel web: {web_url}")
            print("🔧 El servidor web ahora usa conexiones independientes")
            webbrowser.open(web_url)
            
            print("✅ Panel web abierto en el navegador")
            return True
                
        except Exception as e:
            print(f"❌ Error abriendo el panel web: {e}")
            return False
    
    def shutdown(self):
        """Apaga el servidor web"""
        if self.web_server:
            self.web_server.shutdown()
            print("🔴 Servidor web apagado")
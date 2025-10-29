import smtplib
import os
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from datetime import datetime
import cv2
import config

class EmailSender:
    def __init__(self, database_manager):
        self.db = database_manager
        self.email_config = config.EMAIL_CONFIG
    
    def send_detailed_email(self, frame, username, access_type, similarity):
        """Envía correo con detalles completos - VERSIÓN CORREGIDA"""
        try:
            # Verificar configuración de email
            if not self.email_config['sender_password'].strip():
                print("❌ No se configuró contraseña de email")
                return False
            
            # Crear mensaje
            msg = MIMEMultipart()
            msg['From'] = self.email_config['sender_email']
            msg['To'] = self.email_config['receiver_email']
            msg['Subject'] = f"🔐 {access_type} - Sistema Facial - {datetime.now().strftime('%d/%m %H:%M')}"
            
            # Guardar imagen temporalmente
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_path = f"access_{timestamp}.jpg"
            cv2.imwrite(image_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            
            # Obtener historial reciente
            history = self.db.get_access_history(5)
            
            # Crear contenido HTML
            html_content = self._create_email_content(username, access_type, similarity, history)
            msg.attach(MIMEText(html_content, 'html'))
            
            # Adjuntar imagen
            with open(image_path, 'rb') as f:
                img = MIMEImage(f.read(), name=f"acceso_{username}_{timestamp}.jpg")
                msg.attach(img)
            
            # Enviar email
            success = self._send_email(msg)
            
            # Registrar acceso en base de datos
            if success:
                user_id = self.db.get_user_id(username) if access_type == 'PERMITIDO' else None
                
                if hasattr(similarity, 'item'):
                    similarity_db = similarity.item()
                else:
                    similarity_db = float(similarity)
                    
                self.db.log_access(user_id, username, access_type, similarity_db, image_path)
            
            # Limpiar archivo temporal
            time.sleep(1)
            if os.path.exists(image_path):
                os.remove(image_path)
            
            return success
                
        except Exception as e:
            print(f"❌ Error enviando correo: {e}")
            return False
    
    def _create_email_content(self, username, access_type, similarity, history):
        """Crea el contenido HTML del email"""
        # Convertir similitud a float nativo
        if hasattr(similarity, 'item'):
            similarity_float = similarity.item()
        else:
            similarity_float = float(similarity)
        
        # Crear tabla de historial
        history_table = ""
        for access in history:
            similitud = access['similitud']
            if hasattr(similitud, 'item'):
                similitud = similitud.item()
            
            fecha = access['fecha_acceso']
            if isinstance(fecha, str):
                fecha_str = fecha
            else:
                fecha_str = fecha.strftime('%d/%m %H:%M')
            
            history_table += f"""
            <tr>
                <td>{access['nombre_usuario'] or 'Desconocido'}</td>
                <td>{access['tipo_acceso']}</td>
                <td>{fecha_str}</td>
                <td>{similitud if similitud is not None else 'N/A'}</td>
            </tr>
            """
        
        return f"""
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
                        <span>{similarity_float:.3f}</span>
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
    
    def _send_email(self, msg):
        """Envía el email a través del servidor SMTP"""
        try:
            with smtplib.SMTP(self.email_config['smtp_server'], self.email_config['smtp_port']) as server:
                server.starttls()
                server.login(self.email_config['sender_email'], self.email_config['sender_password'])
                server.send_message(msg)
            
            print("✅ Correo con reporte enviado correctamente")
            return True
            
        except smtplib.SMTPAuthenticationError:
            print("❌ Error de autenticación en el servidor de correo")
            print("   Verifica la contraseña de aplicación de Gmail")
        except smtplib.SMTPException as e:
            print(f"❌ Error SMTP: {e}")
        except Exception as e:
            print(f"❌ Error general enviando correo: {e}")
        
        return False
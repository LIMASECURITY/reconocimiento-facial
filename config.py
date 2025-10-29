# Configuración centralizada del sistema
import os

# Configuración de Base de Datos
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456798',
    'database': 'facial_recognition_db'
}

# Configuración de Email
EMAIL_CONFIG = {
    'sender_email': "caquiamir@gmail.com",
    'sender_password': "jgik vjdk ijac jeod", 
    'receiver_email': "l9591667@gmail.com",
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587
}

# Configuración del Sistema
SYSTEM_CONFIG = {
    'known_faces_dir': "usuarios_autorizados",
    'similarity_threshold': 0.6,
    'web_server_port': 8000,
    'admin_password': "123456798"
}

# Configuración de Roles y Usuarios
ROLES_CONFIG = {
    'admin': {
        'password': '123456798',
        'permissions': ['admin_panel', 'view_all_users', 'voice_search', 'view_all_access_history', 'manage_users']
    },
    'user': {
        'permissions': ['register_face', 'verify_access', 'view_own_history']
    }
}
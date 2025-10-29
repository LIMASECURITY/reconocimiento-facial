import cv2
import numpy as np
import os
from datetime import datetime
import config

class FacialRecognition:
    def __init__(self, database_manager):
        self.db = database_manager
        self.known_faces_dir = config.SYSTEM_CONFIG['known_faces_dir']
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        self.known_faces = {}
        
        self.load_known_faces()
    
    def load_known_faces(self):
        """Carga rostros conocidos desde el directorio"""
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
                
                # Sincronizar con base de datos
                self.db.sync_user(name)
                
                img = cv2.imread(path)
                if img is not None:
                    self.known_faces[name] = {
                        'path': path,
                        'features': self.extract_advanced_features(img)
                    }
                    print(f"✅ {name}")
    
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
    
    def recognize_face(self, frame):
        """Reconoce un rostro en el frame capturado"""
        current_features = self.extract_advanced_features(frame)
        
        if current_features is None:
            print("❌ No se detectó rostro")
            return "Desconocido", 0.0
        
        best_match = "Desconocido"
        best_similarity = 0.0
        
        for name, user_data in self.known_faces.items():
            similarity = self.compare_faces(current_features, user_data['features'])
            
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = name
        
        print(f"🔍 Similitud: {best_similarity:.3f}")
        return best_match, best_similarity
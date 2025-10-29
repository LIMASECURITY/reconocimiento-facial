import speech_recognition as sr
import pyttsx3
import threading

class VoiceHandler:
    def __init__(self):
        self.engine = self.setup_voice_engine()
    
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
    
    def voice_search_user(self):
        """Búsqueda de usuario por voz"""
        recognizer = sr.Recognizer()
        microphone = sr.Microphone()
        
        print("🎤 Habla el nombre del usuario que deseas buscar...")
        print("⏰ Tienes 5 segundos para hablar...")
        
        try:
            with microphone as source:
                print("🔇 Calibrando micrófono...")
                recognizer.adjust_for_ambient_noise(source, duration=1)
                print("🎤 Habla ahora...")
                
                audio = recognizer.listen(source, timeout=8, phrase_time_limit=5)
            
            print("🔊 Procesando audio...")
            username = recognizer.recognize_google(audio, language="es-ES")
            print(f"🔍 Reconocido: {username}")
            
            return username.strip().lower()
            
        except sr.WaitTimeoutError:
            print("❌ Tiempo de espera agotado. No se detectó voz.")
        except sr.UnknownValueError:
            print("❌ No se pudo entender el audio. Intenta nuevamente.")
        except sr.RequestError as e:
            print(f"❌ Error en el servicio de reconocimiento: {e}")
        except Exception as e:
            print(f"❌ Error inesperado: {e}")
        
        return None
    
    def speak_text(self, text):
        """Lee texto en voz alta en segundo plano"""
        def speak_in_background():
            try:
                if self.engine:
                    self.engine.say(text)
                    self.engine.runAndWait()
            except Exception as e:
                print(f"⚠️  Error en voz: {e}")
        
        voice_thread = threading.Thread(target=speak_in_background)
        voice_thread.daemon = True
        voice_thread.start()
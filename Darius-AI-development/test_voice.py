import speech_recognition as sr
import os

# Verificar API Key (aunque no se use aquí)
api_key = os.getenv("GEMINI_API_KEY")
print(f"API Key presente: {bool(api_key)}")

# Prueba de reconocimiento de voz
r = sr.Recognizer()
r.energy_threshold = 6000
r.dynamic_energy_threshold = True
r.pause_threshold = 0.8

print("Di algo en español (tienes 5 segundos)...")
with sr.Microphone() as source:
    try:
        audio = r.listen(source, timeout=5, phrase_time_limit=8)
        print("Procesando...")
        text = r.recognize_google(audio, language="es-ES")
        print(f"Texto reconocido: '{text}'")
    except sr.WaitTimeoutError:
        print("No se detectó audio (timeout)")
    except sr.UnknownValueError:
        print("No se pudo entender el audio")
    except sr.RequestError as e:
        print(f"Error de servicio: {e}")
    except Exception as e:
        print(f"Error general: {e}")
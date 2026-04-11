import speech_recognition as sr
import pyttsx3
import os
import datetime
import customtkinter as ctk
import threading
import numpy as np
import tkinter as tk
import time
import sys
import re
import webbrowser
import winreg
import urllib.parse
from pathlib import Path
from difflib import get_close_matches
from google import genai
from google.genai import types

# --- CONFIGURACIÓN DE NÚCLEO ---
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    print("ERROR: No se encontró GEMINI_API_KEY en las variables de entorno.")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)
MODEL_ID = "gemini-2.5-flash"

class DariusFinal(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Configuración de Ventana
        self.title("DARIUS AI - SISTEMA OPERATIVO")
        self.geometry("450x600")
        self.configure(fg_color="#0f0f0f")
        
        # Estados del Sistema
        self.running = True
        self.name = "darius"
        self.is_listening = False
        self.waiting_for_command = False
        self.is_muted = False
        self.installed_apps = {}
        self.browser_path = None
        
        # Inicialización de Motores
        self.tts_engine = pyttsx3.init()
        self.setup_tts()
        self.listener = sr.Recognizer()
        self.configure_listener()
        
        # UI y Aplicaciones
        self.setup_ui()
        self.scan_apps_async()

    def setup_tts(self):
        voices = self.tts_engine.getProperty("voices")
        for v in voices:
            if "spanish" in v.name.lower() or "es" in v.id.lower():
                self.tts_engine.setProperty("voice", v.id)
                break
        self.tts_engine.setProperty("rate", 185)

    def configure_listener(self):
        self.listener.energy_threshold = 6000
        self.listener.dynamic_energy_threshold = True
        self.listener.pause_threshold = 0.8

    def setup_ui(self):
        # Header
        self.label_title = ctk.CTkLabel(self, text="DARIUS AI", font=("Orbitron", 32, "bold"), text_color="#00fbff")
        self.label_title.pack(pady=20)

        self.status_label = ctk.CTkLabel(self, text="SISTEMA LISTO", font=("Arial", 12), text_color="gray")
        self.status_label.pack(pady=5)

        # Visualizador de Ondas (Canvas)
        self.canvas = tk.Canvas(self, width=350, height=100, bg="#0f0f0f", highlightthickness=0)
        self.canvas.pack(pady=10)
        self.lines = [self.canvas.create_rectangle(10+(i*14), 45, 10+(i*14)+8, 55, fill="#00fbff", outline="") for i in range(25)]

        # Consola de Chat
        self.chat_display = ctk.CTkTextbox(self, width=400, height=200, font=("Consolas", 11), state="disabled", fg_color="#1a1a1a")
        self.chat_display.pack(pady=10)

        # Controles
        self.start_btn = ctk.CTkButton(self, text="INICIALIZAR", fg_color="#00fbff", text_color="black", font=("Arial", 14, "bold"), command=self.start_system)
        self.start_btn.pack(pady=10)

        self.mute_btn = ctk.CTkButton(self, text="🔇 MODO SILENCIO", fg_color="#ff5555", state="disabled", command=self.toggle_mute)
        self.mute_btn.pack(pady=5)

    def add_to_chat(self, speaker, text):
        self.chat_display.configure(state="normal")
        ts = datetime.datetime.now().strftime("%H:%M")
        self.chat_display.insert("end", f"[{ts}] {speaker.upper()}: {text}\n")
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def talk(self, text):
        self.add_to_chat("Darius", text)
        def _speak():
            try:
                self.tts_engine.say(text)
                self.tts_engine.runAndWait()
            except: pass
        threading.Thread(target=_speak, daemon=True).start()

    def scan_apps_async(self):
        threading.Thread(target=self.scan_applications, daemon=True).start()

    def scan_applications(self):
        # Escaneo de registro y carpetas (simplificado para el ejemplo)
        # Aquí va tu lógica de winreg y Path.rglob que ya dominas
        self.installed_apps["calculadora"] = "calc"
        self.installed_apps["bloc de notas"] = "notepad"
        self.status_label.configure(text="BASE DE DATOS ACTUALIZADA", text_color="#00ff88")

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        if self.is_muted:
            self.mute_btn.configure(text="🔊 ESCUCHAR", fg_color="#00ff88")
            self.talk("Modo discreto activado.")
        else:
            self.mute_btn.configure(text="🔇 MODO SILENCIO", fg_color="#ff5555")
            self.talk("Sistemas de escucha reactivados.")

    def animate_logic(self):
        if self.is_listening and self.running:
            for line in self.lines:
                h = np.random.randint(5, 80)
                coords = self.canvas.coords(line)
                self.canvas.coords(line, coords[0], 50 - h/2, coords[2], 50 + h/2)
            self.after(80, self.animate_logic)
        else:
            for line in self.lines:
                coords = self.canvas.coords(line)
                self.canvas.coords(line, coords[0], 45, coords[2], 55)

    def start_system(self):
        self.start_btn.configure(state="disabled", text="NÚCLEO ONLINE")
        self.mute_btn.configure(state="normal")
        self.talk("Darius en línea. Esperando órdenes, Oscar.")
        threading.Thread(target=self.main_loop, daemon=True).start()

    def main_loop(self):
        while self.running:
            if not self.is_muted:
                self.listen_and_process()
            time.sleep(0.5)

    def listen_and_process(self):
        with sr.Microphone() as source:
            self.is_listening = True
            self.animate_logic()
            try:
                audio = self.listener.listen(source, timeout=5, phrase_time_limit=8)
                self.is_listening = False
                text = self.listener.recognize_google(audio, language="es-ES").lower()
                
                if self.name in text or self.waiting_for_command:
                    clean_text = text.replace(self.name, "").strip()
                    self.add_to_chat("Oscar", text)
                    self.execute_command(clean_text)
            except:
                self.is_listening = False

    def execute_command(self, cmd):
        # 1. Comandos de Sistema (Apagado/Reinicio)
        if "apagar el equipo" in cmd:
            self.talk("Confirmación requerida para apagar el sistema.")
            # Aquí iría la lógica de confirmación que ya tienes
            return

        # 2. Control de Volumen
        if "subir volumen" in cmd:
            os.system("nircmd.exe changesysvolume 5000") # Requiere nircmd o similar
            self.talk("Volumen incrementado.")
            return

        # 3. Multimedia (YouTube)
        if "reproduce" in cmd or "pon" in cmd:
            song = cmd.replace("reproduce", "").replace("pon", "").strip()
            webbrowser.open(f"https://www.youtube.com/results?search_query={song}")
            self.talk(f"Buscando {song} en YouTube.")
            return

        # 4. Salida
        if any(word in cmd for word in ["cerrar", "adiós", "descansa"]):
            self.talk("Cerrando protocolos. Hasta pronto, Oscar.")
            time.sleep(2)
            self.kill_process()
            return

        # 5. IA (Gemini 2.5)
        self.ask_gemini(cmd)

    def ask_gemini(self, prompt):
        try:
            config = types.GenerateContentConfig(
                system_instruction="Eres Darius, asistente avanzado. Sé breve y futurista.",
                temperature=0.7
            )
            response = client.models.generate_content(model=MODEL_ID, contents=prompt, config=config)
            self.talk(response.text)
        except Exception as e:
            self.talk("Error de enlace con el núcleo Gemini.")

    def kill_process(self):
        self.running = False
        self.destroy()
        sys.exit()

if __name__ == "__main__":
    app = DariusFinal()
    app.mainloop()
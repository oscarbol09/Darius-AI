import datetime

def simulate_talk(text):
    """Simula el método talk() para ver si funciona"""
    print(f"🎤 Darius dice: '{text}'")

    # Simular add_to_chat
    ts = datetime.datetime.now().strftime("%H:%M")
    chat_entry = f"[{ts}] DARIUS: {text}"
    print(f"💬 Agregado al chat: {chat_entry}")

    # Simular voz (no podemos probar realmente, pero mostramos que se intentaría)
    print("🔊 Intentando reproducir voz...")

def test_command_execution(cmd):
    """Simula execute_command para un comando específico"""
    print(f"\n=== Probando comando: '{cmd}' ===")

    # Lógica de execute_command
    if any(word in cmd for word in ["hora", "qué hora", "tiempo", "horas"]):
        current_time = datetime.datetime.now().strftime("%H:%M")
        simulate_talk(f"Son las {current_time}")
        return True

    if any(word in cmd for word in ["fecha", "qué fecha", "día", "fechas"]):
        current_date = datetime.datetime.now().strftime("%d de %B de %Y")
        simulate_talk(f"Hoy es {current_date}")
        return True

    if "calculadora" in cmd or "calc" in cmd:
        simulate_talk("Abriendo calculadora")
        print("🖩 Ejecutando: os.system('calc')")
        return True

    if any(word in cmd for word in ["bloc", "notepad", "notas", "nota"]):
        simulate_talk("Abriendo bloc de notas")
        print("📝 Ejecutando: os.system('notepad')")
        return True

    if "estado" in cmd or "status" in cmd:
        simulate_talk("Sistema operativo funcionando. Comandos básicos disponibles. IA limitada por cuota diaria.")
        return True

    if "subir volumen" in cmd:
        simulate_talk("Volumen incrementado.")
        print("🔊 Ejecutando: os.system('nircmd.exe changesysvolume 5000')")
        return True

    if "reproduce" in cmd or "pon" in cmd:
        song = cmd.replace("reproduce", "").replace("pon", "").strip()
        simulate_talk(f"Buscando {song} en YouTube.")
        print(f"🎵 Ejecutando: webbrowser.open('https://www.youtube.com/results?search_query={song}')")
        return True

    if any(word in cmd for word in ["cerrar", "adiós", "descansa"]):
        simulate_talk("Cerrando protocolos. Hasta pronto, Oscar.")
        print("👋 Cerrando aplicación")
        return True

    # Si llega aquí, iría a Gemini
    print("🤖 Comando iría a Gemini (cuota agotada)")
    simulate_talk("Lo siento, he alcanzado el límite de consultas de IA por hoy. Los comandos básicos siguen funcionando.")
    return False

if __name__ == "__main__":
    # Probar los comandos que vimos en la consola
    test_commands = [
        "qué hora es",
        "hora",
        "calculadora",
        "subir volumen",
        "+ 2"
    ]

    for cmd in test_commands:
        test_command_execution(cmd)
import os
import datetime

def test_basic_commands():
    """Simula execute_command para probar solo comandos básicos"""
    commands = [
        "hora",
        "qué hora es",
        "fecha",
        "calculadora",
        "bloc de notas",
        "subir volumen",
        "reproduce música rock",
        "estado",
        "cerrar"
    ]

    print("=== PRUEBA DE COMANDOS BÁSICOS (sin IA) ===\n")

    for cmd in commands:
        print(f"🎤 Comando: '{cmd}'")

        # Simular la lógica de execute_command (sin Gemini)
        if any(word in cmd for word in ["hora", "qué hora", "tiempo", "horas"]):
            current_time = datetime.datetime.now().strftime("%H:%M")
            print(f"✅ HORA: Son las {current_time}")

        elif any(word in cmd for word in ["fecha", "qué fecha", "día", "fechas"]):
            current_date = datetime.datetime.now().strftime("%d de %B de %Y")
            print(f"✅ FECHA: Hoy es {current_date}")

        elif "calculadora" in cmd or "calc" in cmd:
            print("✅ CALCULADORA: Abriendo calculadora")

        elif any(word in cmd for word in ["bloc", "notepad", "notas", "nota"]):
            print("✅ BLOC: Abriendo bloc de notas")

        elif "subir volumen" in cmd:
            print("✅ VOLUMEN: Volumen incrementado")

        elif "reproduce" in cmd or "pon" in cmd:
            song = cmd.replace("reproduce", "").replace("pon", "").strip()
            print(f"✅ YOUTUBE: Buscando {song} en YouTube")

        elif "estado" in cmd or "status" in cmd:
            print("✅ ESTADO: Sistema operativo funcionando. Comandos básicos disponibles.")

        elif any(word in cmd for word in ["cerrar", "adiós", "descansa"]):
            print("✅ SALIDA: Cerrando protocolos")

        else:
            print(f"🤖 Comando iría a Gemini: '{cmd}'")

        print()

if __name__ == "__main__":
    test_basic_commands()
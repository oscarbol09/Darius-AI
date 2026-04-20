import os
import datetime

def test_commands():
    """Simula execute_command para probar sin voz"""
    commands = [
        "hora",
        "qué hora es",
        "fecha",
        "calculadora",
        "bloc de notas",
        "subir volumen",
        "reproduce música rock",
        "cerrar"
    ]

    for cmd in commands:
        print(f"\n--- Probando comando: '{cmd}' ---")

        # Simular la lógica de execute_command
        if any(word in cmd for word in ["hora", "qué hora", "tiempo", "horas"]):
            current_time = datetime.datetime.now().strftime("%H:%M")
            print(f"✅ Comando reconocido: HORA")
            print(f"Respuesta: Son las {current_time}")
            continue

        if any(word in cmd for word in ["fecha", "qué fecha", "día", "fechas"]):
            current_date = datetime.datetime.now().strftime("%d de %B de %Y")
            print(f"✅ Comando reconocido: FECHA")
            print(f"Respuesta: Hoy es {current_date}")
            continue

        if "calculadora" in cmd or "calc" in cmd:
            print(f"✅ Comando reconocido: CALCULADORA")
            print("Respuesta: Abriendo calculadora")
            continue

        if any(word in cmd for word in ["bloc", "notepad", "notas", "nota"]):
            print(f"✅ Comando reconocido: BLOC DE NOTAS")
            print("Respuesta: Abriendo bloc de notas")
            continue

        if "subir volumen" in cmd:
            print(f"✅ Comando reconocido: VOLUMEN")
            print("Respuesta: Volumen incrementado")
            continue

        if "reproduce" in cmd or "pon" in cmd:
            print(f"✅ Comando reconocido: YOUTUBE")
            song = cmd.replace("reproduce", "").replace("pon", "").strip()
            print(f"Respuesta: Buscando {song} en YouTube")
            continue

        if any(word in cmd for word in ["cerrar", "adiós", "descansa"]):
            print(f"✅ Comando reconocido: SALIDA")
            print("Respuesta: Cerrando protocolos")
            continue

        print(f"🤖 Comando no reconocido, iría a Gemini: '{cmd}'")

if __name__ == "__main__":
    test_commands()
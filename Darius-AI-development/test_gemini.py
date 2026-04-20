import os
from google import genai
from google.genai import types

# Verificar API Key
API_KEY = os.getenv("GEMINI_API_KEY")
print(f"API Key presente: {bool(API_KEY)}")

if not API_KEY:
    print("ERROR: No hay API key")
    exit(1)

try:
    client = genai.Client(api_key=API_KEY)
    MODEL_ID = "gemini-2.5-flash"

    print("Probando Gemini con un prompt simple...")
    config = types.GenerateContentConfig(
        system_instruction="Eres un asistente útil. Responde brevemente.",
        temperature=0.7
    )

    response = client.models.generate_content(model=MODEL_ID, contents="Hola, ¿cómo estás?", config=config)

    print(f"Respuesta cruda: {response}")
    print(f"Tipo de respuesta: {type(response)}")

    # Intentar acceder al texto
    if hasattr(response, 'text'):
        print(f"Texto (response.text): '{response.text}'")
    elif hasattr(response, 'candidates') and response.candidates:
        print(f"Candidatos encontrados: {len(response.candidates)}")
        candidate = response.candidates[0]
        print(f"Candidato: {candidate}")
        if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
            print(f"Parts: {candidate.content.parts}")
            if candidate.content.parts:
                part = candidate.content.parts[0]
                if hasattr(part, 'text'):
                    print(f"Texto del part: '{part.text}'")
                else:
                    print(f"Part no tiene text: {part}")
        else:
            print(f"Candidato no tiene content.parts: {candidate}")
    else:
        print(f"Respuesta no tiene text ni candidates: {dir(response)}")

except Exception as e:
    print(f"Error probando Gemini: {e}")
    import traceback
    traceback.print_exc()
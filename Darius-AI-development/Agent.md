# Agent.md — Contexto Maestro para IA sobre Darius AI

> **Para cualquier IA o asistente de código que trabaje en este proyecto:**
> Lee este documento completo antes de proponer cualquier cambio. Contiene la
> arquitectura real del sistema, las decisiones de diseño ya tomadas y las
> reglas que debes respetar para no romper el comportamiento existente.

---

## 1. ¿Qué es Darius AI?

Darius AI es un **asistente de escritorio con voz para Windows**, construido
íntegramente en Python. Su propósito es ser el copiloto de Oscar en su PC:
ejecuta comandos del sistema operativo por voz, responde preguntas en lenguaje
natural usando Gemini como motor de IA, y lo hace con una personalidad
futurista y directa.

**Principios fundacionales (NO cambiarlos sin discusión):**

1. **Local-first:** La mayoría de comandos se resuelven sin internet y sin
   consumir cuota de API. Gemini es el último recurso, no el primero.
2. **Degradación elegante:** Si Gemini falla → OpenRouter. Si OpenRouter falla
   → mensaje claro y comandos locales activos. El sistema nunca se rompe
   silenciosamente.
3. **Una sola instancia:** Mutex Win32 garantiza que solo corra una copia.
4. **Sin dependencias ocultas:** Toda configuración vive en `config.json`
   (parámetros) y `.env` (secretos). Nada hardcodeado en el código.

---

## 2. Stack tecnológico

| Capa | Tecnología | Motivo |
|------|-----------|--------|
| UI | CustomTkinter + tkinter Canvas | Tema oscuro nativo, sin Electron ni web |
| Voz entrada | SpeechRecognition + PyAudio | Google STT gratuito, es-ES |
| Voz salida | SAPI via win32com (SpVoice) | Integración nativa Windows, voces instaladas |
| IA principal | Google GenAI SDK (`google-genai`) — Gemini 2.5 Flash | Mayor calidad, contexto largo |
| IA fallback | OpenRouter REST API (`urllib`) — modelos :free | Sin dependencia extra, stdlib |
| SO Windows | pywin32, subprocess, PowerShell, winreg | Control total del sistema |
| Config | `config.json` + `python-dotenv` (.env) | Sin recompilación al cambiar parámetros |
| Threading | stdlib `threading` + `queue.Queue` | COM requiere inicialización por hilo |

---

## 3. Estructura de archivos

```
Darius-AI-development/
├── .env                    ← Secretos (GEMINI_API_KEY, OPENROUTER_API_KEY). NO subir a Git.
├── .env.example            ← Plantilla sin valores reales (sí subir a Git).
├── .gitignore              ← Excluye .env, logs, caché, binarios, dist/
├── Agent.md                ← ESTE ARCHIVO — contexto maestro para IAs
├── README.md               ← Documentación técnica completa (arquitectura, threading, etc.)
├── requirements.txt        ← Dependencias pip. Incluye python-dotenv y requests.
├── config.json             ← Parámetros de usuario (nombre, modelo Gemini, mic, TTS…)
├── config_loader.py        ← Carga config.json, expone objeto `cfg` con propiedades tipadas
├── main.py                 ← NÚCLEO — UI, voz, comandos, lógica Gemini + fallback OpenRouter
├── windows_commands.py     ← Catálogo de comandos del SO (paneles, subprocesos PowerShell/CMD)
│
├── darius.log              ← Log rotativo (excluido de Git)
├── chat_history.txt        ← Historial de conversación (excluido de Git)
├── apps_cache.json         ← Caché de apps instaladas, TTL 6h (excluido de Git)
│
├── DARIUS_AI.spec          ← Configuración PyInstaller para compilar a .exe
├── nircmd.exe              ← Utilidad de volumen (fallback si pycaw no disponible)
│
├── debug_inspector_v6.py   ← Script de diagnóstico y testing (no tocar en producción)
├── test_commands_v6.py     ← Tests de comandos del SO
├── test_gemini_v6.py       ← Tests de integración con Gemini API
└── test_voice_v6.py        ← Tests del subsistema de voz
```

---

## 4. Flujo de datos principal

```
USUARIO HABLA / ESCRIBE
        │
        ▼
[Modo PTT]  ────────────────┐
[Modo NOMBRE] ──────────────┤  → Google STT (es-ES)  →  texto transcrito
[Modo AUTO]  ───────────────┘
                                      │
                         process_recognized_text()
                           (filtra por nombre si aplica)
                                      │
                              execute_command(cmd)
                                      │
               ┌──────────────────────┴────────────────────────┐
               │ ¿coincide _CMD_PATTERNS?                      │ No
               ▼                                               ▼
        handler local                                   ask_gemini(cmd)
        (_cmd_hora, _cmd_abrir,                                │
         _cmd_accion → windows_commands.py…)         ┌────────┴──────────┐
               │                                     │ Gemini OK         │ Gemini falla
               ▼                                     ▼                   ▼
           talk(respuesta)                     respuesta            _ask_openrouter()
                │                                   │              (modelo random :free)
                ▼                                   │                    │
         tts_queue.put()                            └────────────────────┘
                │                                            │
         [tts-worker]                                   talk(respuesta)
       SAPI.SpVoice.Speak()
```

---

## 5. Arquitectura del sistema de IA (Gemini + Fallback)

### 5.1 Gemini (primario)

- Cliente: `google-genai` SDK, `genai.Client(api_key=...)`
- Modelo: `gemini-2.5-flash` (configurable en `config.json`)
- Historial: `conversation_history` como lista de dicts `{role, parts}`, ventana
  de `GEMINI_HISTORY_TURNS * 2` mensajes
- System instruction: generada por `_build_system_instruction()` — centralizada
  y compartida con el fallback

### 5.2 OpenRouter (fallback automático)

- Activado cuando Gemini lanza cualquier excepción no crítica
- Función: `_ask_openrouter(prompt, system_instruction)` — nivel módulo (no clase)
- Protocolo: REST a `https://openrouter.ai/api/v1/chat/completions` via `urllib`
  (sin dependencias extra)
- Modelos: lista `_OPENROUTER_MODELS` barajada aleatoriamente en cada intento
- Reintentos: itera la lista completa antes de rendirse
- Config requerida: `OPENROUTER_API_KEY` en `.env`

**Lista de modelos fallback (actualizable sin tocar lógica):**
```python
_OPENROUTER_MODELS = [
    "nvidia/nemotron-3-super:free",
    "meta-llama/llama-3-8b-instruct:free",
    "mistralai/mistral-7b-instruct:free",
    "arcee-ai/arcee-trinity:free",
    "google/gemma-3-4b-it:free",
    "microsoft/phi-3-mini-128k-instruct:free",
    "qwen/qwen3-8b:free",
]
```

Para agregar un modelo: simplemente añadir el string a la lista. No hay más cambios.

### 5.3 Árbol de decisión de errores

```
Exception en Gemini
    │
    ├── is_auth_error  (API_KEY / UNAUTHENTICATED)
    │       └─→ talk("Error de autenticación…") — NO activa fallback
    │
    ├── is_network_error  (network / connection / unreachable)
    │       └─→ talk("Sin conexión…") — NO activa fallback
    │
    └── cualquier otro error (cuota, timeout, 503, etc.)
            └─→ _ask_openrouter()
                    │
                    ├── OK  → respuesta al usuario
                    └── Falla → talk("Motores no disponibles…") — comandos locales activos
```

---

## 6. Módulos clave y sus responsabilidades

### `main.py`

- **NO modificar** la sección de mutex (instancia única) — rompe el comportamiento deseado
- **NO eliminar** el `finally: self.set_status("LISTO", "gray")` pattern — la UI se queda colgada
- El `load_dotenv()` debe estar **antes** de cualquier `os.getenv()` — ya está en la línea correcta
- El threading model es delicado: toda llamada a la UI debe hacerse con `self.after(0, fn)`,
  nunca directamente desde un hilo daemon

### `config_loader.py`

- Es el single source of truth para parámetros operativos
- `cfg` es una instancia global importada con `from config_loader import cfg`
- `cfg.set(value, *keys)` persiste cambios en `config.json` en tiempo real
- Los defaults en `_DEFAULTS` garantizan arranque seguro sin `config.json`

### `windows_commands.py`

- Completamente stateless y thread-safe
- Para agregar un nuevo panel del SO: agregar entrada en `WINDOWS_COMMANDS` con
  `cmd`, `aliases`, `desc`
- Para agregar una nueva acción: agregar entrada en `SYSTEM_ACTIONS` con
  `action.type`, `action.run`, `aliases`, `desc`; y opcionalmente
  `confirm: True`, `return_output: True`, `open_window: True`
- La normalización de aliases (sin tildes, minúsculas) es automática
- El cutoff fuzzy es 0.52 para acciones del SO — **no bajar** o habrá falsos positivos

### `.env`

- Leído por `python-dotenv` al arrancar `main.py`
- Variables disponibles:
  - `GEMINI_API_KEY` — **obligatoria**
  - `OPENROUTER_API_KEY` — para el fallback
  - `PORCUPINE_ACCESS_KEY` — opcional, para wake-word por hardware

---

## 7. Variables de entorno y configuración

### Secretos (`.env`, NO en Git)
```
GEMINI_API_KEY="..."
OPENROUTER_API_KEY="..."
PORCUPINE_ACCESS_KEY=""   # opcional
```

### Parámetros de usuario (`config.json`, SÍ en Git)
```json
{
  "assistant": { "name": "darius", "user_name": "Oscar" },
  "gemini":    { "model": "gemini-2.5-flash", "max_tokens": 300,
                 "temperature": 0.7, "history_turns": 10 },
  "tts":       { "rate": 1, "volume": 100 },
  "microphone":{ "energy_threshold": 3000, "pause_threshold": 0.8,
                 "listen_timeout": 5, "phrase_limit": 10 },
  "listen_mode": "NOMBRE",
  "listen_key": "right ctrl",
  "name_similarity_cutoff": 0.60
}
```

---

## 8. Reglas de estilo de código

Estas convenciones están presentes en toda la base de código existente.
**Respétalas en cualquier modificación:**

1. **Separadores de sección:** Usar la línea de 77 guiones `# ─────...─────`
   para separar bloques mayores dentro de un archivo
2. **Docstrings:** Solo en funciones públicas y métodos no triviales. Formato
   libre en español, sin Google style ni NumPy style
3. **Type hints:** Usar en firmas de funciones públicas. `str | None` (Python
   3.10+ union syntax) en lugar de `Optional[str]`
4. **Nombres de hilos:** Siempre pasar `name=` en `threading.Thread()` para
   facilitar el diagnóstico en logs
5. **Logging:** Usar el logger `log = logging.getLogger("DARIUS")` (o
   subnombradores como `"DARIUS.Config"`). Nunca usar `print()` en producción
6. **Imports al inicio del archivo**, excepto imports condicionales dentro de
   hilos daemon (ej: `pythoncom`, `audioop`) que tienen dependencias de
   inicialización por hilo
7. **`self.after(0, fn)`** para toda actualización de UI desde hilos daemon.
   Nunca modificar widgets directamente desde un hilo no-main
8. **Constantes de módulo en SCREAMING_SNAKE_CASE**, variables de instancia en
   `snake_case`, clases en `PascalCase`
9. **Alineación vertical** en asignaciones múltiples relacionadas:
   ```python
   GEMINI_MODEL     = cfg.GEMINI_MODEL
   GEMINI_MAX_TOKENS = cfg.GEMINI_MAX_TOKENS
   ```
10. **`try/except Exception`** (amplio) solo en puntos de entrada de hilos y
    llamadas externas. En lógica interna usar excepciones específicas

---

## 9. Extensiones planificadas (Roadmap v7+)

Estas features están diseñadas pero no implementadas. No las implementes sin
que Oscar lo pida explícitamente:

- **Mem0 (memoria persistente):** Recordar preferencias y contexto entre
  sesiones via MCP. El hook en `ask_gemini()` está planificado como Tool Use
  antes de la llamada principal
- **Tavily (búsqueda web en tiempo real):** Para preguntas sobre datos
  actuales. También via Function Calling en Gemini
- **n8n (automatización de flujos):** Webhooks para disparar flujos n8n desde
  comandos de voz. La arquitectura de `_cmd_accion` puede extenderse con un
  handler `_cmd_webhook()`
- **MCP dinámico (v8):** Cargar herramientas MCP desde un directorio de plugins

---

## 10. Cómo hacer cambios seguros

### Agregar un comando de voz nuevo

1. Ir a `windows_commands.py`
2. Agregar en `SYSTEM_ACTIONS` (si ejecuta algo del SO) o en `WINDOWS_COMMANDS`
   (si abre una ventana/panel)
3. No tocar `main.py` — el router lo resuelve automáticamente

### Cambiar parámetros de comportamiento

1. Editar `config.json` directamente
2. O usar `cfg.set(valor, "clave1", "clave2")` en runtime

### Agregar un modelo de fallback OpenRouter

1. Abrir `main.py`
2. Agregar el model string a `_OPENROUTER_MODELS`
3. Listo — la lógica de shuffle e iteración ya existe

### Cambiar la personalidad/prompt de Darius

1. Editar el método `_build_system_instruction()` en `DariusFinal`
2. El cambio aplica a Gemini Y al fallback OpenRouter automáticamente

### Depurar problemas de IA

1. Revisar `darius.log` — todos los errores de Gemini y OpenRouter se loggean
2. Las líneas `[Gemini]`, `[OpenRouter]` y `[Fallback]` están diseñadas para
   ser grep-eables

---

## 11. Dependencias y cómo instalarlas

```bash
# Entorno virtual (recomendado)
python -m venv .venv
.venv\Scripts\activate

# Todas las dependencias
pip install -r requirements.txt

# La librería keyboard requiere ejecutar como administrador para modo PTT
```

**Dependencias críticas:**
- `python-dotenv` — carga el `.env` (nuevo en v6.2)
- `google-genai` — SDK de Gemini
- `pywin32` — SAPI TTS + mutex Win32 (solo Windows)
- `SpeechRecognition` + `PyAudio` — captura de voz

---

*Documento generado en base al análisis completo de `main.py` v6.x,
`windows_commands.py`, `config_loader.py` y `README.md`.
Actualizar este archivo siempre que se agreguen nuevas features, módulos
o decisiones de arquitectura importantes.*

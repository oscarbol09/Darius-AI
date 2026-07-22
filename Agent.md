# Agent.md — Contexto Maestro para IA sobre Darius AI

> **Para cualquier IA o asistente de código que trabaje en este proyecto:**
> Lee este documento completo antes de proponer cualquier cambio. Contiene la
> arquitectura real del sistema, las decisiones de diseño ya tomadas y las
> reglas que debes respetar para no romper el comportamiento existente.
>
> Ultima actualizacion: Auditoria tecnica completa — Abril 2026.

---

## 1. Que es Darius AI?

Darius AI es un **asistente de escritorio con voz para Windows**, construido
integramente en Python. Su proposito es ser el copiloto de Oscar en su PC:
ejecutar comandos del sistema operativo por voz, responder preguntas en lenguaje
natural usando Gemini como motor de IA, y hacerlo con una personalidad
futurista y directa.

**Principios fundacionales (NO cambiarlos sin discusion):**

1. **Local-first:** La mayoria de comandos se resuelven sin internet y sin
   consumir cuota de API. Gemini es el ultimo recurso, no el primero.
2. **Degradacion elegante:** Si Gemini falla -> OpenRouter. Si OpenRouter falla
   -> mensaje claro y comandos locales activos. El sistema nunca se rompe
   silenciosamente.
3. **Una sola instancia:** Mutex Win32 garantiza que solo corra una copia.
4. **Sin dependencias ocultas:** Toda configuracion vive en `config.json`
   (parametros) y `.env` (secretos). Nada hardcodeado en el codigo.

---

## 2. Stack tecnologico

| Capa | Tecnologia | Motivo |
|------|-----------|--------|
| UI | CustomTkinter + tkinter Canvas | Tema oscuro nativo, sin Electron ni web |
| Voz entrada | SpeechRecognition + PyAudio | Google STT gratuito, es-ES |
| Voz salida | SAPI via win32com (SpVoice) | Integracion nativa Windows, voces instaladas |
| IA principal | Google GenAI SDK (`google-genai`) - Gemini 2.5 Flash | Mayor calidad, contexto largo |
| IA fallback | OpenRouter REST API (`urllib`) - modelos :free | Sin dependencia extra, stdlib |
| SO Windows | pywin32, subprocess, PowerShell, winreg | Control total del sistema |
| Config | `config.json` + `python-dotenv` (.env) | Sin recompilacion al cambiar parametros |
| Threading | stdlib `threading` + `queue.Queue` | COM requiere inicializacion por hilo |

---

## 3. Estructura de archivos actual

```
Darius-AI/
├── .env                     <- Secretos (GEMINI_API_KEY, OPENROUTER_API_KEY). NO subir a Git.
├── .env.example             <- Plantilla sin valores reales (si subir a Git).
├── .gitignore               <- Excluye .env, *.log, cache, binarios, .vscode/, .venv/
├── .github/
│   └── workflows/
│       └── main_darius-ai.yml  <- CI: ruff + pytest + gitleaks + pip-audit
├── Agent.md                 <- ESTE ARCHIVO — contexto maestro para IAs
├── README.md                <- Documentacion tecnica completa
├── requirements.txt         <- Deps para Railway / Linux (Streamlit)
├── requirements-windows.txt <- Deps para desarrollo local en Windows (main.py)
├── config.json              <- Parametros de usuario (nombre, modelo Gemini, mic, TTS...)
├── config_loader.py         <- Carga config.json, expone objeto `cfg` con propiedades tipadas
├── main.py                  <- NUCLEO — UI, voz, comandos, logica Gemini + fallback OpenRouter
├── windows_commands.py      <- Catalogo de comandos del SO (paneles, subprocesos PowerShell/CMD)
├── app.py                   <- Interfaz web Streamlit
│
├── darius.log               <- Log rotativo (excluido de Git — patron *.log)
├── chat_history.txt         <- Historial de conversacion (excluido de Git)
├── apps_cache.json          <- Cache de apps instaladas, TTL 6h (excluido de Git)
│
├── debug_inspector_v6.py    <- Script de diagnostico y testing (no usar en produccion)
├── test_commands_v6.py      <- Tests de comandos del SO
├── test_gemini_v6.py        <- Tests de integracion con Gemini API
└── test_voice_v6.py         <- Tests del subsistema de voz
```

> **Nota sobre Git:** Las carpetas `.venv/` y `.vscode/` estan en `.gitignore`.
> Si aparecen rastreadas en el repositorio remoto, eliminarlas del indice con:
> ```bash
> git rm -r --cached .venv/
> git rm -r --cached .vscode/
> git commit -m "chore: remove .venv and .vscode from tracking"
> git push
> ```

---

## 4. Flujo de datos principal

```
USUARIO HABLA / ESCRIBE
        |
        v
[Modo PTT]   ─────────────────┐
[Modo NOMBRE] ────────────────┤  -> Google STT (es-ES)  ->  texto transcrito
[Modo AUTO]  ─────────────────┘
                                      |
                         process_recognized_text()
                           (filtra por nombre si aplica)
                                      |
                              execute_command(cmd)
                               [limpia nombre del cmd]
                                      |
               ┌──────────────────────┴────────────────────────┐
               │ coincide _CMD_PATTERNS?                        │ No
               v                                                v
        handler local                                    ask_gemini(cmd)
        (_cmd_hora, _cmd_abrir,                                 |
         _cmd_accion -> windows_commands.py...)       ┌─────────┴──────────┐
               |                                      │ Gemini OK          │ Gemini falla
               v                                      v                    v
           talk(respuesta)                      respuesta            _ask_openrouter()
                |                                    |              (modelo random :free)
                v                                    |                     |
         tts_queue.put()                             └─────────────────────┘
                |                                             |
         [tts-worker]                                    talk(respuesta)
       SAPI.SpVoice.Speak()
       [DETACHED_PROCESS — independiente del proceso principal]
```

---

## 5. Arquitectura del sistema de IA (Gemini + Fallback)

### 5.1 Gemini (primario)

- Cliente: `google-genai` SDK, `genai.Client(api_key=...)`
- Modelo: `gemini-2.5-flash` (configurable en `config.json`)
- `max_output_tokens`: **800** — suficiente para respuestas completas sin truncar
- Historial: `conversation_history` como lista de dicts `{role, parts}`, ventana
  de `GEMINI_HISTORY_TURNS * 2` mensajes
- System instruction: generada por `_build_system_instruction()` — centralizada
  y compartida con el fallback
- Extraccion de texto: fallback progresivo (`response.text` -> `candidates[0].content.parts[0].text`)
  con validacion de `finish_reason` para detectar respuestas truncadas o bloqueadas

### 5.2 OpenRouter (fallback automatico)

- Activado cuando Gemini lanza cualquier excepcion no critica
- Funcion: `_ask_openrouter(prompt, system_instruction)` — nivel modulo (no clase)
- Protocolo: REST a `https://openrouter.ai/api/v1/chat/completions` via `urllib`
  (sin dependencias extra, usa stdlib)
- Timeout: **20 segundos** por modelo (captura explicita de `TimeoutError`)
- Validacion de respuesta: comprueba que `choices` no este vacio y que `content`
  tenga texto antes de retornar — evita respuestas silenciosamente vacias
- Modelos: lista `_OPENROUTER_MODELS` barajada aleatoriamente en cada intento
- Reintentos: itera la lista completa antes de rendirse
- Config requerida: `OPENROUTER_API_KEY` en `.env`

**Lista de modelos fallback (actualizable sin tocar logica):**
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

Para agregar un modelo: simplemente anadir el string a la lista.

### 5.3 Como Darius decide que modelo usar (arbol de decision)

```
Usuario envia prompt -> no coincide ningun patron local
        |
        v
  ask_gemini(prompt)
        |
        ├── Gemini responde OK ───────────────────────────────► talk(respuesta)
        |
        └── Exception en Gemini
                |
                ├── is_auth_error  (API_KEY / UNAUTHENTICATED)
                │       └─► talk("Error de autenticacion...") — sin fallback
                |
                ├── is_network_error  (network / connection / unreachable)
                │       └─► talk("Sin conexion...") — sin fallback
                |
                └── cualquier otro error (cuota, timeout, 503, respuesta vacia)
                        └─► _ask_openrouter() — itera modelos aleatorios
                                |
                                ├── OK ──► talk(respuesta)
                                |
                                └── Todos fallan
                                        └─► talk("Motores no disponibles...")
                                             comandos locales siguen activos
```

**Resumen clave:** Gemini siempre es el primero. OpenRouter es el respaldo automatico.
Los comandos locales (paneles del SO, acciones PowerShell) NUNCA dependen de IA.

---

## 6. Dependencias Windows (`requirements-windows.txt`)

```
google-genai>=1.0.0        # SDK Gemini (genai.Client)
requests>=2.31.0           # HTTP auxiliar
python-dotenv>=1.0.0       # Carga .env antes de os.getenv()
customtkinter>=5.2.0       # UI escritorio tema oscuro
SpeechRecognition>=3.10.0  # STT (Google es-ES)
PyAudio>=0.2.14            # Captura de audio del microfono
pywin32>=306               # win32com (SAPI TTS), win32event (mutex), winreg
comtypes>=1.2.0            # Interfaz COM requerida por pycaw
pycaw>=20181226            # Control de volumen por hardware (IAudioEndpointVolume)
keyboard>=0.13.5           # Push-to-Talk (requiere ejecutar como administrador)
numpy>=1.24.0              # Calculo de nivel de audio RMS para animacion de ondas
streamlit>=1.35.0          # Web UI (app.py, pruebas locales)
```

**Opcional (mejora experiencia, no requerida para arrancar):**
- `pvporcupine` + `pyaudio` — wake word por hardware (requiere `PORCUPINE_ACCESS_KEY`)

---

## 7. Modulos clave y sus responsabilidades

### `main.py`

- **NO modificar** la seccion de mutex (instancia unica) — rompe el comportamiento deseado
- **NO eliminar** el patron `finally: self.set_status("LISTO", "gray")` — la UI queda colgada
- El `load_dotenv()` debe estar **antes** de cualquier `os.getenv()` — ya esta correcto
- Toda actualizacion de widgets desde hilos daemon debe hacerse con `self.after(0, fn)`

### `config_loader.py`

- Single source of truth para parametros operativos
- `cfg` es una instancia global importada con `from config_loader import cfg`
- `cfg.set(value, *keys)` persiste cambios en `config.json` en tiempo real
- Los defaults en `_DEFAULTS` garantizan arranque seguro incluso sin `config.json`
- `max_tokens` por defecto: **800** (ajustado en auditoria para evitar truncado)

### `windows_commands.py`

- Completamente stateless y thread-safe
- **Bug del foco corregido:** `_launch()` usa `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`
  para que comandos como `msconfig`, `taskmgr` o `regedit` sean procesos totalmente
  independientes de Darius. Esto elimina el bug donde el proceso heredaba el contexto
  de ventana del hilo TTS y abria el reproductor de audio en lugar del programa pedido.
- Para agregar un panel del SO: anadir entrada en `WINDOWS_COMMANDS` con `cmd`, `aliases`, `desc`
- Para anadir una accion: anadir entrada en `SYSTEM_ACTIONS` con `action.type`, `action.run`,
  `aliases`, `desc`; y opcionalmente `confirm: True`, `return_output: True`, `open_window: True`
- Cutoffs fuzzy: `_WIN_CUTOFF = 0.68` (paneles), `_ACT_CUTOFF = 0.75` (acciones)

### `.env`

- Leido por `python-dotenv` al arrancar `main.py`
- Variables:
  - `GEMINI_API_KEY` — **obligatoria**
  - `OPENROUTER_API_KEY` — para el fallback
  - `PORCUPINE_ACCESS_KEY` — opcional, wake-word por hardware

---

## 8. Variables de entorno y configuracion

### Secretos (`.env`, NO en Git)
```
GEMINI_API_KEY="tu_clave_aqui"
OPENROUTER_API_KEY="tu_clave_aqui"
PORCUPINE_ACCESS_KEY=""   # opcional
```

### Parametros de usuario (`config.json`, SI en Git)
```json
{
  "assistant": { "name": "darius", "user_name": "Oscar" },
  "gemini":    { "model": "gemini-2.5-flash", "max_tokens": 800,
                 "temperature": 0.7, "history_turns": 10 },
  "tts":       { "rate": 1, "volume": 100 },
  "microphone":{ "energy_threshold": 3000, "pause_threshold": 0.8,
                 "listen_timeout": 5, "phrase_limit": 10 },
  "listen_mode": "NOMBRE",
  "listen_key": "right ctrl",
  "name_similarity_cutoff": 0.60
}
```

> **Importante:** `max_tokens` fue subido de 300 a **800** en la auditoria de Abril 2026
> para evitar que las respuestas de Gemini se corten antes de completarse.

---

## 9. Reglas de estilo de codigo

1. **Separadores de seccion:** linea de 77 guiones `# ─────...─────`
2. **Docstrings:** solo en funciones publicas y metodos no triviales, en espanol
3. **Type hints:** en firmas publicas. Usar `str | None` (Python 3.10+)
4. **Nombres de hilos:** siempre pasar `name=` en `threading.Thread()`
5. **Logging:** usar `log = logging.getLogger("DARIUS")`. Nunca `print()` en produccion
6. **Imports** al inicio del archivo, excepto imports condicionales en hilos daemon
7. **`self.after(0, fn)`** para toda actualizacion de UI desde hilos daemon
8. **Constantes** en SCREAMING_SNAKE_CASE, instancias en snake_case, clases en PascalCase
9. **`try/except Exception`** amplio solo en puntos de entrada de hilos y llamadas externas

---

## 10. Extensiones planificadas (Roadmap v7+)

- **Mem0 (memoria persistente):** Recordar preferencias entre sesiones via MCP
- **Tavily (busqueda web):** Datos actuales via Function Calling en Gemini
- **n8n (automatizacion):** Webhooks disparados por comandos de voz
- **MCP dinamico (v8):** Cargar herramientas MCP desde un directorio de plugins

---

## 11. Comandos rapidos de mantenimiento

```bash
# Activar entorno virtual
.venv\Scripts\activate

# Instalar dependencias Windows
pip install -r requirements-windows.txt

# Limpiar archivos que no deberian estar en Git
git rm -r --cached .venv/
git rm -r --cached .vscode/
git commit -m "chore: remove .venv and .vscode from tracking"
git push

# Ver que esta rastreado actualmente
git ls-files --cached

# Ejecutar Darius (como administrador para modo PTT)
python main.py
```

---

*Documento reescrito en auditoria tecnica completa sobre codigo real:
`main.py` v6.x, `windows_commands.py`, `config_loader.py`, `config.json`,
`requirements-windows.txt` y `.gitignore`. Abril 2026.*

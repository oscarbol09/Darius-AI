# Agent.md — Contexto Maestro para IA sobre Darius AI

> **Para cualquier IA o asistente de código que trabaje en este proyecto:**
> Lee este documento completo antes de proponer cualquier cambio. Contiene la
> arquitectura real del sistema, las decisiones de diseño ya tomadas y las
> reglas que debes respetar para no romper el comportamiento existente.
>
> Ultima actualizacion: Ruff 208→0, limpieza repo, rutas completas en subprocess — Julio 2026.

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
├── .gitignore               <- Excluye .env, *.log, cache, .vscode/, .venv/, supabase/migrations/, docs/
├── .github/
│   └── workflows/
│       └── main_darius-ai.yml  <- CI: ruff + pytest + gitleaks + pip-audit
├── Agent.md                 <- ESTE ARCHIVO — contexto maestro para IAs
├── README.md                <- Documentacion tecnica completa
├── requirements.txt         <- Deps para Railway / Linux (Streamlit)
├── requirements-windows.txt <- Deps para desarrollo local en Windows (main.py)
├── config.json              <- Parametros de usuario
├── config_loader.py         <- Carga config.json, expone objeto `cfg` con propiedades snake_case
├── main.py                  <- NUCLEO — UI, voz, comandos, IA
├── windows_commands.py      <- Catalogo de comandos del SO (_PS, _CMD, _MMC, _CONTROL con rutas completas)
├── app.py                   <- Interfaz web Streamlit
├── voice_filter.py          <- Filtro de nombre en texto (check_name_in_text)
├── ai_client.py             <- Clientes Gemini + OpenRouter
├── tts_worker.py            <- Worker TTS (SAPI) en hilo propio
├── edge_tts_engine.py       <- Blueprint: TTS edge-tts (cross-platform)
├── stt_engine.py            <- Blueprint: STT con backends intercambiables
├── supabase_client.py       <- Cliente Supabase compartido
│
├── tests/
│   ├── test_commands_v6.py  <- Tests de comandos del SO
│   ├── test_voice_v6.py     <- Tests del subsistema de voz
│   ├── test_gemini_v6.py    <- Tests de integracion con Gemini API
│   ├── test_config_loader.py<- Tests de config_loader
│   └── test_supabase_client.py <- Tests de supabase_client
│
├── pyproject.toml           <- Configuracion Ruff (line-length=120), pytest, coverage
├── Dockerfile               <- Contenedor multi-etapa (Railway)
├── requirements-dev.txt     <- Dependencias de desarrollo
├── CHANGELOG.md             <- Historial de versiones
├── CONTRIBUTING.md          <- Guia de contribucion
├── SECURITY.md              <- Politica de seguridad
│
├── darius.log               <- Log rotativo (excluido de Git)
├── chat_history.txt         <- Historial de conversacion (excluido de Git)
└── apps_cache.json          <- Cache de apps instaladas, TTL 6h (excluido de Git)
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
        (_cmd_hora, _cmd_abrir,                                  |
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
                └── otro error (API, timeout, parse, rate limit)
                        └─► _ask_openrouter(prompt, system_instruction)
                                |
                                ├── Exito ──► talk(respuesta)
                                │
                                └── Falla en todos los modelos
                                        └─► talk("No pude obtener respuesta...")
```

---

## 6. Decisiones arquitectonicas clave

(En adelante, "D" = Decision, seguido de un titulo descriptivo y su fundamento.)

### D1 — Gemini como IA principal, OpenRouter como fallback

**Decision:** Gemini es el motor principal por su calidad superior y menor latencia.
OpenRouter con modelos gratuitos es el plan B, sin dependencias extra (solo stdlib).
No se implementa un reintento sobre el mismo modelo fallido — se pasa al siguiente.

### D2 — TTS en hilo separado con cola de mensajes

**Decision:** `TTSWorker` corre en su propio thread con `pythoncom.CoInitialize()` y
una `queue.Queue`. Esto evita que el habla bloquee la UI o el reconocimiento de voz.
`wait_until_done()` permite pausar la escucha mientras Darius habla.

### D3 — Mutex Win32 para instancia unica

**Decision:** `win32event.CreateMutex` con nombre global. Si ya existe, muestra un
messagebox y sale con `sys.exit(0)`. Simple, nativo, no requiere archivo PID.

### D4 — DETACHED_PROCESS para comandos del SO

**Decision:** Todos los subprocesos de `windows_commands.py` usan
`creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`. Esto evita que el
proceso hijo herede la consola de Darius y compita por el foco de audio o ventana.
Rutas completas (_PS, _CMD, _MMC, _CONTROL) via `os.environ["SystemRoot"]`.

### D5 — config_loader con merge de 3 fuentes (local > defaults < Supabase)

**Decision:** La configuracion se construye como merge jerarquico:
1. `_DEFAULTS` (hardcodeado en `config_loader.py`)
2. `config.json` local (valores del usuario)
3. Supabase (tabla `config`) — si esta disponible, tiene prioridad y se cachea
   en `config.json` para arranques offline.
Propiedades de `cfg` usan snake_case (`cfg.assistant_name`, `cfg.gemini_model`).

### D6 — No se usa `shell=True` (seguridad)

**Decision:** `shell=False` siempre que sea posible. Los comandos PowerShell/CMD
se pasan como listas de argumentos. En `_launch()` (linea 882) se usa
`["cmd", "/c", cmd]` en vez de `cmd` directamente, para evitar inyeccion de
comandos via nombres de archivo maliciosos.

### D7 — Sin base de datos local; Supabase es opcional

**Decision:** Darius funciona completamente offline sin Supabase. Si
`SUPABASE_URL`/`SUPABASE_KEY` no estan en `.env`, `get_supabase()` retorna `None`
y todo el sistema sigue funcionando en modo local. La tabla `config` en Supabase
permite compartir configuracion entre `main.py` y `app.py`.

### D8 — Ruff con reglas estrictas, 0 errores

**Decision:** Se mantiene `ruff check` en CI con `line-length=120`. Todo el codigo
pasa sin errores ni advertencias. Excepciones documentadas con `# noqa`:
- `S310` en urlopen con URLs hardcodeadas (OpenRouter, YouTube)
- `S603` en subprocess donde el input proviene de un dict controlado
- `S606` en `os.startfile()` (API correcta de Windows)
- `S607` en `nircmd.exe` (tercero, sin ruta fija)
- `E501` en data dictionary de `windows_commands.py`

---

## 7. Modos de escucha (PTT / NOMBRE / AUTO)

### Modo PTT (Push-to-Talk)
- Activacion: mantener presionada una tecla (`LISTEN_KEY`, default `right ctrl`)
- Mientras se mantiene presionada: graba audio continuamente en buffer
- Al soltar: envia a Google STT y procesa
- Visual: icono verde con indicador de habla
- Ventaja: sin falsos positivos, control total del usuario

### Modo NOMBRE
- Darius ignora todo el audio hasta que detecta su nombre
- Deteccion: `check_name_in_text()` — busqueda exacta + fuzzy con `SequenceMatcher`
  (umbral `NAME_SIMILARITY_CUTOFF`, default 0.60)
- Despues del nombre: procesa el resto del texto como comando
- Si el texto tiene muchas palabras (≥ `MIN_WORDS_WITHOUT_NAME`, default 99):
  asume que es una conversacion con Gemini y no requiere nombre

### Modo AUTO
- Combina NOMBRE + envio directo a Gemini
- Si hay nombre: procesa comando local
- Si no hay nombre: envia directo a Gemini como conversacion
- Util para charlas rapidas sin necesidad de activacion explicita

### Logica de `process_recognized_text()`:
```python
# En cada modo:
#   - PTT: todo el texto es comando
#   - NOMBRE: solo si detecta nombre; puede ir directamente a Gemini
#   - AUTO: prioriza comandos locales, resto a Gemini
#   - Si es nombre exacto (p.ej. "darius" solo): Darius responde "Dime"
```

---

## 8. Base de datos de aplicaciones (apps_cache.json)

Darius mantiene un cache local de aplicaciones instaladas para abrirlas por voz.

**Formato:**
```json
{
    "chrome": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "spotify": "C:\\Users\\oscar\\AppData\\Roaming\\Spotify\\Spotify.exe",
    "vscode": "C:\\Users\\oscar\\AppData\\Local\\Programs\\Microsoft VS Code\\Code.exe",
    "_meta": {
        "cached_at": "2026-04-05T12:00:00",
        "version": 6
    }
}
```

- Carga perezosa: solo escanea `%ProgramData%\Microsoft\Windows\Start Menu` al
  arrancar si el cache tiene mas de `APP_CACHE_HOURS` horas.
- No bloquea el arranque: si el scan falla, se usa el cache existente.
- `find_app(name)`: hace fuzzy match del nombre contra las keys del cache.

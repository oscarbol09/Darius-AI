# DARIUS AI — Documentación Técnica Oficial

> **Versión del documento:** 1.0.0  
> **Versión del software:** 6.x (rama `main`)  
> **Última actualización:** 2026  
> **Stack:** Python 3.11+ · CustomTkinter · Google GenAI · SAPI · Win32

---

## Índice

1. [Visión General y Filosofía de Diseño](#1-visión-general-y-filosofía-de-diseño)
2. [Arquitectura del Sistema](#2-arquitectura-del-sistema)
3. [Módulo Core — `main.py`](#3-módulo-core--mainpy)
   - 3.1 [Ciclo de Vida de la Aplicación](#31-ciclo-de-vida-de-la-aplicación)
   - 3.2 [Modos de Activación](#32-modos-de-activación)
   - 3.3 [Gestión de Concurrencia y Threading](#33-gestión-de-concurrencia-y-threading)
   - 3.4 [Motor de Resolución de Comandos Locales](#34-motor-de-resolución-de-comandos-locales)
4. [Inteligencia de Sistema Operativo — `windows_commands.py`](#4-inteligencia-de-sistema-operativo--windows_commandspy)
   - 4.1 [Tipo A — Lanzamiento de Paneles y URIs](#41-tipo-a--lanzamiento-de-paneles-y-uris)
   - 4.2 [Tipo B — Subprocesos y Acciones del Sistema](#42-tipo-b--subprocesos-y-acciones-del-sistema)
   - 4.3 [Algoritmo de Resolución de Comandos](#43-algoritmo-de-resolución-de-comandos)
5. [Flujo de Procesamiento End-to-End](#5-flujo-de-procesamiento-end-to-end)
6. [Especificaciones Técnicas](#6-especificaciones-técnicas)
7. [Instalación y Configuración](#7-instalación-y-configuración)
8. [Roadmap — Integración MCP](#8-roadmap--integración-mcp)

---

## 1. Visión General y Filosofía de Diseño

DARIUS AI es un **asistente virtual de escritorio nativo para Windows**, construido sobre un modelo de capas desacopladas que separa la interfaz gráfica, el razonamiento conversacional y la ejecución de comandos del sistema operativo. El sistema está diseñado bajo tres principios fundamentales:

**Localidad primero:** La gran mayoría de comandos operativos (diagnóstico de red, gestión de energía, información del sistema, etc.) se resuelven de forma completamente local mediante subprocesos `subprocess` y APIs de PowerShell/CMD, sin latencia de red y sin consumir cuota de la API de Gemini.

**Degradación elegante:** Cuando el servicio de IA externo no está disponible (error 429, sin conectividad, cuota agotada), el sistema continúa operando con todas sus capacidades locales intactas. El usuario recibe retroalimentación verbal clara sobre el estado del servicio.

**Extensibilidad modular:** La adición de nuevos comandos del sistema operativo se realiza de forma declarativa en los diccionarios `WINDOWS_COMMANDS` y `SYSTEM_ACTIONS` de `windows_commands.py`, sin necesidad de modificar la lógica de `main.py`.

---

## 2. Arquitectura del Sistema

El sistema se organiza en tres capas con dependencias unidireccionales (de superior a inferior):

```
┌─────────────────────────────────────────────────────────────────┐
│                    CAPA DE PRESENTACIÓN (UI)                    │
│              CustomTkinter · tkinter · Canvas                   │
│   DariusFinal(ctk.CTk) — hilo principal del event loop de Tk   │
├─────────────────────────────────────────────────────────────────┤
│                    NÚCLEO DE APLICACIÓN                         │
│  ┌───────────────────┐   ┌──────────────────┐   ┌───────────┐  │
│  │   Speech Engine   │   │  Command Router  │   │  Gemini   │  │
│  │  (sr + SAPI TTS)  │   │  (_CMD_PATTERNS) │   │  Client   │  │
│  └───────────────────┘   └──────────────────┘   └───────────┘  │
│       Hilos daemon            Hilo principal          Hilo      │
│  [tts-worker] [audio-monitor] [main/ptt/wake-word]  [gemini]   │
├─────────────────────────────────────────────────────────────────┤
│             CAPA DE ABSTRACCIÓN DEL SISTEMA OPERATIVO           │
│                      windows_commands.py                        │
│   ┌────────────────────────┐   ┌──────────────────────────┐    │
│   │  WINDOWS_COMMANDS      │   │  SYSTEM_ACTIONS           │    │
│   │  Tipo A — URIs/Paneles │   │  Tipo B — Subprocesos    │    │
│   └────────────────────────┘   └──────────────────────────┘    │
│           os.startfile · subprocess · powershell · cmd          │
└─────────────────────────────────────────────────────────────────┘
         ↕                          ↕
   Win32 API / SAPI          Google GenAI API
```

### Contratos entre capas

| Llamada | Origen | Destino | Retorno |
|---|---|---|---|
| `wincmd_launch(query)` | `main.py` | `windows_commands.py` | `str` (desc) \| `None` |
| `wincmd_resolve_action(query)` | `main.py` | `windows_commands.py` | `dict` \| `None` |
| `wincmd_run_action(entry)` | `main.py` | `windows_commands.py` | `tuple[bool, str]` |
| `gemini_client.models.generate_content(...)` | `main.py` | Google GenAI | `GenerateContentResponse` |

---

## 3. Módulo Core — `main.py`

### 3.1 Ciclo de Vida de la Aplicación

El ciclo de vida sigue la secuencia:

```
1. Bootstrap
   ├─ Mutex Win32 (instancia única)
   ├─ Configuración de logging (archivo + stdout)
   ├─ Validación de GEMINI_API_KEY
   └─ DariusFinal.__init__()
       ├─ setup_tts_config()     → enumera voces SAPI, selecciona español
       ├─ configure_listener()  → calibra energía del micrófono (1s)
       ├─ setup_ui()            → construye widgets CustomTkinter
       ├─ _start_tts_worker()   → lanza hilo daemon TTS
       └─ scan_apps_async()     → lanza hilo de escaneo de apps instaladas

2. Inicio del sistema (botón "INICIALIZAR" → start_system())
   ├─ Selección de loop según listen_mode:
   │   ├─ PTT  → _ptt_loop()        (hilo: ptt-loop)
   │   ├─ AUTO/NOMBRE + Porcupine → _porcupine_loop() (hilo: wake-word)
   │   └─ AUTO/NOMBRE sin Porcupine → main_loop()     (hilo: main-loop)
   └─ _start_audio_level_monitor()  → hilo: audio-monitor

3. Loop activo
   └─ Ciclo: escucha → reconocimiento STT → filtrado → execute_command()
              ↓ (no hay match local)
           ask_gemini()  ← hilo: gemini

4. Cierre (kill_process())
   ├─ self.running = False (señal a todos los loops)
   ├─ Drain de tts_queue (deadline 5s)
   ├─ tts_queue.put(None) → termina el worker TTS
   ├─ self.destroy()      → destruye la ventana Tkinter
   ├─ CloseHandle(mutex)
   └─ sys.exit(0)
```

**Garantía de instancia única:** Al iniciar, `main.py` invoca `win32event.CreateMutex()` con el nombre `Global\DariusAI_SingleInstance`. Si `win32api.GetLastError()` retorna `ERROR_ALREADY_EXISTS`, la aplicación muestra un `messagebox` y termina inmediatamente con `sys.exit(0)`, evitando múltiples instancias concurrentes.

```python
_MUTEX_NAME   = "Global\\DariusAI_SingleInstance"
_mutex_handle = win32event.CreateMutex(None, False, _MUTEX_NAME)
if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
    mb.showerror("DARIUS AI", "Ya hay una instancia de Darius en ejecución.")
    sys.exit(0)
```

---

### 3.2 Modos de Activación

DARIUS implementa tres modos de activación configurables en tiempo de ejecución desde la UI. La constante `DEFAULT_LISTEN_MODE` define el modo al arrancar (por defecto: `LISTEN_MODE_NAME`).

#### Modo PTT (Push-to-Talk)

El hilo `_ptt_loop` realiza **polling a 50 Hz** sobre el estado de `LISTEN_KEY` (por defecto: `right ctrl`) usando `keyboard.is_pressed()`. La captura de audio ocurre en un hilo separado (`ptt-capture`) para no bloquear el loop de polling.

**Flujo PTT:**
1. Flanco descendente en `LISTEN_KEY` → `_ptt_active = True`, UI muestra "HABLANDO…"
2. `pyaudio` graba frames `paInt16` a 16 kHz mientras la tecla permanezca pulsada
3. Flanco ascendente → los frames se serializan en un buffer `io.BytesIO` como WAV en memoria
4. `sr.AudioFile` + `recognize_google(language="es-ES")` transcribe el audio
5. El nombre del asistente se elimina del texto resultante pero **no se exige** — el usuario ya tomó la decisión consciente de presionar la tecla

```python
wav_buffer = io.BytesIO()
with wave.open(wav_buffer, "wb") as wf:
    wf.setnchannels(channels)
    wf.setsampwidth(2)      # paInt16 = 2 bytes por muestra
    wf.setframerate(rate)
    wf.writeframes(raw)
wav_buffer.seek(0)

with sr.AudioFile(wav_buffer) as source:
    audio = self.listener.record(source)
text = self.listener.recognize_google(audio, language="es-ES").lower()
```

#### Modo NOMBRE (Wake-word por software)

El hilo `main_loop` escucha continuamente, pero el texto transcrito solo se procesa si **contiene el nombre del asistente** (`darius`) o una variante fonética cuya similitud sea `≥ NAME_SIMILARITY_CUTOFF` (0.60) medida con `SequenceMatcher`.

El filtro acepta el nombre en cualquier posición de la frase:

```python
def _check_name_in_text(self, text: str) -> tuple[bool, str]:
    # 1. Nombre exacto en cualquier posición
    if ASSISTANT_NAME in text:
        clean = text.replace(ASSISTANT_NAME, "").strip()
        return True, clean

    # 2. Primera palabra similar (variante fonética / error STT)
    if words:
        similarity = SequenceMatcher(None, ASSISTANT_NAME, words[0]).ratio()
        if similarity >= NAME_SIMILARITY_CUTOFF:
            clean = " ".join(words[1:]).strip()
            return True, clean

    return False, text
```

La constante `MIN_WORDS_WITHOUT_NAME = 99` desactiva efectivamente el procesamiento de frases sin nombre, protegiendo contra activaciones espurias por ruido de fondo transcrito como una sola palabra.

#### Modo AUTO (Procesamiento Universal)

Equivalente al comportamiento pre-v6. El loop `main_loop` invoca `process_recognized_text()` que acepta cualquier transcripción sin filtrar el nombre, ofreciendo la máxima comodidad cuando el usuario es el único presente en el entorno.

#### Comparativa de modos

| Característica | PTT | NOMBRE | AUTO |
|---|---|---|---|
| Hilo de captura | `ptt-loop` + `ptt-capture` | `main-loop` | `main-loop` |
| Requiere nombre | No | Sí (o variante ≥ 0.60) | No (se elimina si presente) |
| Grabación continua | No (solo con tecla) | Sí | Sí |
| Privacidad | Alta | Media | Baja |
| Latencia | Inmediata | Media (espera STT) | Media |
| Dependencia extra | `keyboard` | Ninguna | Ninguna |

---

### 3.3 Gestión de Concurrencia y Threading

DARIUS opera bajo un modelo de **threading cooperativo** donde el hilo principal es exclusivamente el event loop de Tkinter. Todas las operaciones bloqueantes se delegan a hilos `daemon=True` para garantizar que nunca congelen la UI.

#### Inventario de hilos

| Nombre del hilo | Origen | Función | Sincronización |
|---|---|---|---|
| `MainThread` | Tkinter | Event loop UI | — |
| `tts-worker` | `_start_tts_worker()` | Despacho serial de TTS via SAPI | `queue.Queue` + `threading.Event` |
| `audio-monitor` | `_start_audio_level_monitor()` | Muestreo de nivel RMS para animación | Variable `_current_audio_level` |
| `main-loop` | `start_system()` | Escucha continua (modos NOMBRE/AUTO) | `is_speaking.Event` |
| `ptt-loop` | `start_system()` | Polling de tecla PTT a 50 Hz | `_ptt_active` flag |
| `ptt-capture` | `_ptt_loop()` | Captura y transcripción PTT | Spawn por evento |
| `wake-word` | `start_system()` | Loop Porcupine (opcional) | `is_speaking.Event` |
| `gemini` | `execute_command()` | Llamada a API Gemini | Spawn por comando |
| `action` | `_execute_action()` | Ejecución de subprocesos del SO | Spawn por comando |
| `app-scanner` | `scan_apps_async()` | Escaneo del registro + filesystem | — |
| `text-cmd` | `_on_text_submit()` | Procesamiento de entrada de texto | Spawn por evento |

#### Worker TTS y prevención de condiciones de carrera

El worker TTS es el único componente con acceso a `SAPI.SpVoice`. Opera sobre una `queue.Queue` con semántica FIFO, usando `threading.Event` (`is_speaking`) para comunicar su estado a los loops de escucha:

```python
def _start_tts_worker(self):
    def worker():
        import pythoncom
        pythoncom.CoInitialize()   # COM debe inicializarse por hilo en Win32
        speaker = win32com.client.Dispatch("SAPI.SpVoice")
        # ...
        while True:
            text = self.tts_queue.get()
            if text is None:          # señal de terminación
                break
            try:
                self.is_speaking.set()
                speaker.Speak(text)
            finally:
                self.is_speaking.clear()
                time.sleep(SPEAKING_TAIL_SECS)   # evita solapamiento de frases
                self.tts_queue.task_done()
        pythoncom.CoUninitialize()
    threading.Thread(target=worker, daemon=True, name="tts-worker").start()
```

La llamada `pythoncom.CoInitialize()` es mandatoria porque el modelo COM de Windows **requiere inicialización por hilo**; omitirla produce un `CoInitialize has not been called` fatal en el hilo TTS.

Los loops de escucha verifican `is_speaking.is_set()` antes de procesar audio entrante, eliminando el efecto de retroalimentación acústica donde DARIUS se escucharía a sí mismo.

---

### 3.4 Motor de Resolución de Comandos Locales

Antes de escalar a la API de Gemini, `execute_command()` recorre una tabla de patrones de expresiones regulares compiladas (`_CMD_PATTERNS`) en orden de prioridad:

```python
_CMD_PATTERNS = [
    (re.compile(r"\b(qué hora|hora exacta)\b"),                   "_cmd_hora"),
    (re.compile(r"\b(qué fecha|fecha de hoy|día de hoy)\b"),      "_cmd_fecha"),
    (re.compile(r"\b(reproduce|pon|ponme|música)\b"),             "_cmd_youtube"),
    (re.compile(r"\b(busca|buscar|googlea)\b"),                   "_cmd_buscar"),
    (re.compile(r"\b(abre|abrir|lanza|ejecuta|inicia)\b"),        "_cmd_abrir"),
    # ...
    (re.compile(r"\b(ver|muéstrame|diagnostica|vacía|...)\b"),    "_cmd_accion"),
]
```

El handler `_cmd_accion` delega la resolución a `windows_commands.py`. Si ningún patrón produce match, el comando se escalada a `ask_gemini()` en un hilo dedicado.

**Confirmación de acciones destructivas:** Las entradas de `SYSTEM_ACTIONS` con `"confirm": True` (ej: `vaciar_papelera`, `resetear_red`, `cerrar_sesion`) activan un flujo de confirmación de dos pasos. El estado `_pending_action` persiste en la instancia hasta que el usuario dice "confirmar" o "cancelar":

```python
if entry.get("confirm", False):
    self._pending_action = entry
    self.talk(f"Estás a punto de ejecutar: {entry['desc']}. "
              "Di confirmar para proceder o cancelar para abortar.")
```

---

## 4. Inteligencia de Sistema Operativo — `windows_commands.py`

Este módulo encapsula la totalidad del conocimiento sobre la API del sistema operativo Windows. Expone tres funciones públicas y ningún estado mutable global, siendo completamente thread-safe para lecturas concurrentes.

### 4.1 Tipo A — Lanzamiento de Paneles y URIs

El diccionario `WINDOWS_COMMANDS` mapea conceptos semánticos a **comandos de apertura de ventanas**. Cada entrada soporta los siguientes tipos de destino:

| Tipo de `cmd` | Mecanismo de lanzamiento | Ejemplo |
|---|---|---|
| URI `ms-settings:*` | `os.startfile(cmd)` | `ms-settings:network` |
| URI de protocolo custom | `os.startfile(cmd)` | `windowsdefender:` |
| Snap-in MMC (`.msc`) | `subprocess.Popen(["mmc", cmd])` | `devmgmt.msc` |
| Applet de Panel de Control (`.cpl`) | `subprocess.Popen(["control", cmd])` | `ncpa.cpl` |
| Ruta de ejecutable | `os.startfile(cmd)` | `C:\...\brave.exe` |
| Carpeta shell especial | `os.startfile(cmd)` | `shell:Downloads` |
| Comando de shell | `subprocess.Popen(cmd, shell=True)` | `explorer`, `calc` |

El campo `fallback_cmd` permite una cadena de fallback para ejecutables de ruta fija (ej: navegadores) que podrían no estar en la ruta estándar:

```python
"brave": {
    "cmd": r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
    "fallback_cmd": "start brave",
    "desc": "Brave Browser"
},
```

La función interna `_launch()` implementa la lógica de dispatching con procesos desenganchados para evitar robos de foco:

```python
def _launch(cmd: str, fallback_cmd: Optional[str] = None) -> bool:
    detached = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    if re.match(r"^[a-z\-]+:", cmd) and not cmd.endswith(".exe"):
        os.startfile(cmd); return True
    if cmd.endswith(".msc"):
        subprocess.Popen(["mmc", cmd], creationflags=detached); return True
    if cmd.endswith(".cpl"):
        subprocess.Popen(["control", cmd], creationflags=detached); return True
    if Path(cmd).is_file():
        os.startfile(cmd); return True
    subprocess.Popen(["cmd", "/c", cmd], creationflags=detached); return True
```

### 4.2 Tipo B — Subprocesos y Acciones del Sistema

El diccionario `SYSTEM_ACTIONS` mapea conceptos operativos a **subprocesos ejecutables** con control preciso sobre captura de salida y visibilidad de ventana. Cada acción se define con los siguientes campos:

| Campo | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `action.type` | `str` | Sí | `"powershell"` \| `"cmd"` |
| `action.run` | `str` | Sí | Comando completo a ejecutar |
| `desc` | `str` | Sí | Descripción para TTS y logs |
| `aliases` | `list[str]` | Sí | Variantes semánticas del trigger |
| `confirm` | `bool` | No | Solicita confirmación verbal antes de ejecutar |
| `return_output` | `bool` | No | Captura stdout/stderr para lectura TTS |
| `open_window` | `bool` | No | Abre consola visible (`CREATE_NEW_CONSOLE`) |

La función `run_action()` implementa tres modos de ejecución mutuamente excluyentes:

```python
def run_action(action_entry: dict) -> tuple[bool, str]:
    if open_window:
        # Abre consola visible — salida no capturada, el usuario la ve en pantalla
        subprocess.Popen(["powershell", "-NoExit", "-Command", run],
                         creationflags=subprocess.CREATE_NEW_CONSOLE)
        return True, ""

    elif return_out:
        # Captura stdout para síntesis TTS, timeout 15s
        result = subprocess.run(
            ["powershell", "-NonInteractive", "-Command", run],
            capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace"
        )
        output = (result.stdout or result.stderr or "Sin salida").strip()
        if len(output) > 300:
            output = output[:300] + "…"   # limita longitud para TTS
        return True, output

    else:
        # Ejecución en background, sin ventana, sin captura
        subprocess.Popen(
            ["powershell", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", run],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return True, ""
```

El flag `CREATE_NO_WINDOW` en el modo background es crítico para evitar el parpadeo de consolas CMD en aplicaciones de escritorio con interfaz gráfica.

#### Ejemplos representativos del catálogo de acciones

```python
"ver ip": {
    "action": {"type": "powershell",
               "run": "(Get-NetIPAddress -AddressFamily IPv4 | "
                      "Where-Object {$_.InterfaceAlias -notlike '*Loopback*'} | "
                      "Select-Object -First 1).IPAddress"},
    "return_output": True,          # DARIUS lee la IP en voz alta
    "desc": "Consultar IP local"
},
"resetear red": {
    "action": {"type": "cmd",
               "run": "netsh winsock reset && netsh int ip reset && ipconfig /flushdns"},
    "confirm": True,                # requiere confirmación verbal
    "desc": "Restablecer configuración de red (Winsock + TCP/IP + DNS)"
},
"ver conexiones activas": {
    "action": {"type": "cmd", "run": "netstat -ano"},
    "return_output": True,
    "open_window": True,            # abre consola visible
    "desc": "Ver conexiones de red activas"
},
```

---

### 4.3 Algoritmo de Resolución de Comandos

El motor de resolución opera sobre **tablas planas de aliases normalizados** construidas en tiempo de módulo (`_build_table()`). La normalización elimina tildes y convierte a minúsculas:

```python
def _normalize(text: str) -> str:
    for src, dst in zip("áéíóúüñàèìòù", "aeiouunaeiou", strict=True):
        text = text.replace(src, dst)
    return text.lower().strip()

def _build_table(source: dict) -> tuple[dict, list]:
    table = {}
    for canonical, data in source.items():
        table[_normalize(canonical)] = canonical
        for alias in data.get("aliases", []):
            table[_normalize(alias)] = canonical   # todos los aliases → canonical key
    return table, list(table.keys())
```

La función central `_resolve()` aplica tres estrategias en cascada con **cortocircuito al primer match**:

```
query (texto del usuario)
       │
       ▼
┌─────────────────────────────────────────────────────────┐
│ 1. EXACT MATCH                                          │
│    _normalize(query) ∈ table → retorna canonical_key   │
│    Tiempo: O(1) — lookup en dict                        │
└──────────────────────────┬──────────────────────────────┘
                           │ sin match
                           ▼
┌─────────────────────────────────────────────────────────┐
│ 2. FUZZY MATCHING (SequenceMatcher)                     │
│    Para cada key en tabla plana (~500 entradas):        │
│      ratio = SequenceMatcher(nq, k).ratio()             │
│    Si max(ratio) ≥ cutoff (0.52) → retorna canonical   │
│    Tiempo: O(n) — lineal sobre el tamaño de la tabla    │
└──────────────────────────┬──────────────────────────────┘
                           │ ratio < 0.52
                           ▼
┌─────────────────────────────────────────────────────────┐
│ 3. KEYWORD SUBSET                                       │
│    Si len(words) ≥ 2:                                   │
│      Para cada key: all(w in key for w in words)       │
│    Tiempo: O(n·m) — n=tabla, m=palabras del query      │
└──────────────────────────┬──────────────────────────────┘
                           │ sin match
                           ▼
                        None → fallback a Gemini o app scanner
```

El umbral `cutoff=0.52` fue calibrado empíricamente para balancear recall (capturar variantes coloquiales) y precision (evitar falsos positivos entre comandos con palabras clave similares). Las tablas `_WIN_TABLE` y `_ACT_TABLE` se construyen **una sola vez al importar el módulo**, evitando reconstrucciones repetidas en cada llamada.

---

## 5. Flujo de Procesamiento End-to-End

El siguiente diagrama describe la trayectoria completa desde la entrada de audio hasta la ejecución o respuesta:

```
USUARIO HABLA
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│ CAPTURA DE AUDIO                                        │
│ Modo PTT  → pyaudio frame buffer (mientras tecla)       │
│ Modo NOMBRE/AUTO → sr.Microphone.listen(timeout=5s)     │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
               Google STT (es-ES)
               sr.recognize_google()
                         │
              ┌──────────┴──────────────┐
              │ UnknownValueError       │ OK
              ▼                        ▼
           (descarta)        process_recognized_text()
                                       │
                          ┌────────────┴────────────────┐
                          │ Modo NOMBRE                 │ Modo PTT/AUTO
                          ▼                             ▼
                   _check_name_in_text()          acepta directo
                   ┌──────┴──────┐
                   │ no encontrado│ encontrado
                   ▼             ▼
                (descarta)  execute_command(clean_text)
                                       │
                         ┌─────────────┴─────────────────┐
                         │ _pending_action is not None    │ None
                         ▼                               ▼
                 _handle_confirmation()      Scan _CMD_PATTERNS
                                                       │
                                          ┌────────────┴────────────┐
                                          │ match regex             │ no match
                                          ▼                         ▼
                                   handler local              ask_gemini()
                                   (_cmd_hora, _cmd_abrir…)         │
                                          │                  ┌──────┴──────────┐
                                          │                  │ API OK          │ Error 429/Net
                                          │                  ▼                 ▼
                                          │           Respuesta Gemini    "Límite diario
                                          │                  │             alcanzado…"
                                          │                  ▼
                                          └──────→ talk(respuesta) → tts_queue.put()
                                                                             │
                                                                        [tts-worker]
                                                                    SAPI.SpVoice.Speak()
```

### Manejo de errores de cuota API

```python
except Exception as e:
    err = str(e)
    if any(k in err for k in ["429", "RESOURCE_EXHAUSTED", "quota"]):
        self.talk("Límite diario de consultas alcanzado. Comandos locales activos.")
    elif any(k in err for k in ["API_KEY", "authentication", "UNAUTHENTICATED"]):
        self.talk("Error de autenticación con el servicio de IA.")
    elif any(k in err.lower() for k in ["network", "connection"]):
        self.talk("Sin conexión a internet.")
```

El sistema diferencia entre error de cuota (degradación a comandos locales), error de autenticación (configuración inválida) y error de conectividad (sin internet), ofreciendo diagnóstico verbal preciso en cada caso.

---

## 6. Especificaciones Técnicas

### Entorno de ejecución

| Requisito | Valor mínimo | Recomendado |
|---|---|---|
| Sistema operativo | Windows 10 (19041) | Windows 11 |
| Python | 3.10 | 3.11+ |
| RAM disponible | 256 MB | 512 MB |
| Micrófono | Cualquier entrada de audio reconocida por Windows | — |
| Conectividad | Requerida solo para STT y Gemini | — |

### Variables de entorno

| Variable | Requerida | Descripción |
|---|---|---|
| `GEMINI_API_KEY` | **Obligatoria** | API key de Google AI Studio |
| `OPENROUTER_API_KEY` | Opcional | API key de OpenRouter para fallback |
| `PORCUPINE_ACCESS_KEY` | Opcional | API key de Picovoice para wake-word por hardware (`pvporcupine`) |

### Dependencias y justificación técnica

| Paquete | Versión | Rol en el sistema |
|---|---|---|
| `google-genai` | latest | SDK oficial de Google GenAI para Gemini 2.5 Flash |
| `SpeechRecognition` | ≥3.10 | Abstracción sobre Google STT via `recognize_google()` |
| `PyAudio` | ≥0.2.14 | Acceso a dispositivos de audio via PortAudio (micrófono + monitor de nivel) |
| `customtkinter` | ≥5.2 | Framework UI con tema oscuro nativo sobre Tkinter |
| `pywin32` (`win32com`, `win32event`, `win32api`, `winerror`) | ≥306 | SAPI TTS, mutex Win32, manejo de handles del SO |
| `pycaw` | latest | Control de volumen via `IAudioEndpointVolume` (Core Audio API) |
| `keyboard` | ≥0.13 | Polling de teclas en modo PTT (requiere ejecución como administrador) |
| `numpy` | ≥1.24 | Cálculo de amplitud para animación de ondas en Canvas |
| `difflib` (stdlib) | — | `SequenceMatcher` para fuzzy matching y `get_close_matches` para app scanner |
| `winreg` (stdlib) | — | Lectura del Registro de Windows para escaneo de apps instaladas |
| `pvporcupine` + `pyaudio` | Opcional | Wake-word por hardware de Picovoice (mayor precisión que modo NOMBRE) |

### Parámetros de configuración centralizada

Todos los parámetros operativos se definen como constantes en la sección de configuración de `main.py`:

```python
GEMINI_MODEL         = "gemini-2.5-flash"
GEMINI_MAX_TOKENS    = 800
GEMINI_TEMPERATURE   = 0.7
GEMINI_HISTORY_TURNS = 10        # ventana de contexto conversacional (turnos)
MIC_ENERGY_THRESHOLD = 3000      # umbral mínimo de energía de activación
MIC_PAUSE_THRESHOLD  = 0.8       # segundos de silencio para finalizar frase
MIC_LISTEN_TIMEOUT   = 5         # segundos máximos esperando inicio de voz
MIC_PHRASE_LIMIT     = 10        # segundos máximos de duración de frase
APP_CACHE_HOURS      = 6         # TTL del caché de apps instaladas
SPEAKING_TAIL_SECS   = 0.4       # pausa post-TTS antes de volver a escuchar
NAME_SIMILARITY_CUTOFF = 0.60    # umbral mínimo para aceptar variante del nombre
```

### Caché de aplicaciones instaladas

El escáner de aplicaciones (`_scan_applications`) combina tres fuentes:

1. **Registro de Windows:** Tres rutas de `Uninstall` (HKLM 64-bit, HKLM 32-bit, HKCU) extrayendo `DisplayName` + `InstallLocation`
2. **Filesystem scan:** `rglob("*.exe")` sobre `%PROGRAMFILES%`, `%PROGRAMFILES(X86)%` y `%LOCALAPPDATA%\Programs`
3. **Diccionario base:** Comandos canónicos de Windows siempre disponibles (`calc`, `notepad`, `explorer`, etc.)

El resultado se persiste en `apps_cache.json` con timestamp. El TTL de 6 horas (`APP_CACHE_HOURS`) evita el costo de re-escaneo en cada arranque. La búsqueda fuzzy sobre el índice usa `difflib.get_close_matches(cutoff=0.55)`.

---

## 7. Instalación y Configuración

### Instalación del entorno

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/darius-ai.git
cd darius-ai

# 2. Crear y activar entorno virtual
python -m venv .venv
.venv\Scripts\activate

# 3. Instalar dependencias (Windows)
pip install -r requirements-windows.txt

# 4. (Opcional) Instalar soporte PTT
pip install keyboard

# 5. (Opcional) Instalar wake-word por hardware
pip install pvporcupine pyaudio
```

> **Nota sobre `keyboard`:** La librería `keyboard` requiere **privilegios de administrador** para leer eventos globales de teclado en Windows. Ejecuta el script como administrador o desde un terminal elevado si usas el modo PTT.

### Configuración de variables de entorno

```powershell
# PowerShell — configuración permanente para el usuario actual
[System.Environment]::SetEnvironmentVariable(
    "GEMINI_API_KEY",
    "tu-api-key-aqui",
    "User"
)

# Opcional — para pvporcupine
[System.Environment]::SetEnvironmentVariable(
    "PORCUPINE_ACCESS_KEY",
    "tu-porcupine-key-aqui",
    "User"
)
```

### Ejecución

```bash
# Modo estándar
python main.py

# Como ejecutable compilado (PyInstaller)
# El archivo DARIUS_AI.spec ya está configurado en el repositorio
pyinstaller DARIUS_AI.spec
```

---

## 8. Roadmap — Integración MCP

La arquitectura de DARIUS AI está preparada para incorporar capacidades de **memoria persistente entre sesiones** y **búsqueda web en tiempo real** a través del protocolo **MCP (Model Context Protocol)**, exponiéndolas como herramientas de función (*Function Calling*) en las llamadas a la API de Gemini.

### Arquitectura objetivo con MCP

```
ask_gemini(prompt)
      │
      ▼
gemini_client.models.generate_content(
    model="gemini-2.5-flash",
    contents=conversation_history,
    tools=[
        Tool(function_declarations=[mem0_search_fn, mem0_store_fn]),
        Tool(function_declarations=[tavily_search_fn]),
    ]
)
      │
      ├─ response.candidates[0].content.parts → type == "function_call"
      │         │
      │    ┌────┴─────────────────────────────┐
      │    │ mem0_search / mem0_store          │ tavily_search
      │    ▼                                  ▼
      │  Mem0 MCP Server                 Tavily MCP Server
      │  (memoria semántica persistente) (búsqueda web en tiempo real)
      │         │                              │
      │    function_response              function_response
      │         └────────────┬─────────────────┘
      │                      ▼
      └─── Segunda llamada a Gemini con tool_result → respuesta final
```

### Componente 1: Mem0 — Memoria Persistente

**Problema que resuelve:** DARIUS actualmente olvida todo al cerrar (`reset_conversation()` o cierre de proceso). La integración con Mem0 permitirá recordar preferencias del usuario, rutinas habituales, contexto de proyectos activos y cualquier información que el usuario haya compartido en sesiones anteriores.

**Implementación prevista:**

```python
# Declaración de herramientas para Gemini Function Calling
mem0_tools = [
    {
        "name": "mem0_store_memory",
        "description": "Almacena un hecho o preferencia del usuario en memoria persistente",
        "parameters": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "Información a memorizar"},
                "category": {"type": "string", "enum": ["preference", "fact", "task", "context"]}
            },
            "required": ["content"]
        }
    },
    {
        "name": "mem0_search_memory",
        "description": "Recupera memorias relevantes para el contexto actual",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Consulta semántica"}
            },
            "required": ["query"]
        }
    }
]
```

**Casos de uso concretos:**
- "Darius, mi proyecto principal se llama ATLAS y está en `D:\Proyectos\Atlas`" → memorizado y disponible en sesiones futuras
- "Darius, abre mi proyecto de trabajo" → recupera el contexto y ejecuta `os.startfile(ruta_almacenada)`
- Recordar preferencias de volumen, modo de activación preferido, alias personalizados de aplicaciones

### Componente 2: Tavily — Búsqueda Web en Tiempo Real

**Problema que resuelve:** El modelo Gemini tiene una fecha de corte de conocimiento. Las consultas sobre noticias recientes, precios actuales, estado de servicios web, documentación actualizada o cualquier información dinámica requieren búsqueda web real.

**Implementación prevista:**

```python
tavily_tool = {
    "name": "tavily_search",
    "description": (
        "Realiza una búsqueda web en tiempo real. Úsala cuando el usuario pregunte "
        "por noticias recientes, precios, clima, estado de servicios, o cualquier "
        "información que pueda haber cambiado después de tu fecha de entrenamiento."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "search_depth": {"type": "string", "enum": ["basic", "advanced"]},
            "max_results": {"type": "integer", "default": 3}
        },
        "required": ["query"]
    }
}
```

**Casos de uso concretos:**
- "Darius, ¿cuál es el precio actual del dólar?"
- "Darius, ¿hay alguna actualización de Python esta semana?"
- "Darius, ¿cómo está el tráfico en la autopista norte?"

### Plan de implementación por fases

| Fase | Hito | Descripción |
|---|---|---|
| **v7.0** | Function Calling base | Refactorizar `ask_gemini()` para procesar `function_call` responses y ejecutar un ciclo de herramientas |
| **v7.1** | Mem0 Integration | Conectar servidor MCP de Mem0, implementar `mem0_store` automático al detectar información personal |
| **v7.2** | Tavily Integration | Conectar servidor MCP de Tavily, calibrar el prompt del sistema para que Gemini use la herramienta cuando el contexto lo requiera |
| **v7.3** | Memory-Aware Context | Inyectar memorias relevantes en el `system_instruction` de cada llamada a Gemini, personalizando la experiencia por usuario |
| **v8.0** | MCP Dinámico | Arquitectura de plugins MCP: cargar/descargar herramientas en tiempo de ejecución desde un directorio de configuración |

### Consideraciones de privacidad para MCP

Toda la información enviada a Mem0 y Tavily transitará por servicios externos. Las versiones futuras deberán implementar:
- **Filtrado de datos sensibles** antes de almacenar en Mem0 (contraseñas, números de tarjeta, datos personales críticos)
- **Modo offline de Mem0** usando un backend local SQLite como alternativa al servicio cloud
- **Transparencia verbal:** DARIUS notificará al usuario cuando esté almacenando información o realizando búsquedas web

---

## Contribución y Convenciones

### Agregar nuevos comandos del SO

Para extender el catálogo sin tocar `main.py`, agrega entradas al diccionario correspondiente en `windows_commands.py`:

```python
# Tipo A — nueva ventana/panel
"mi_nuevo_panel": {
    "cmd": "ms-settings:nuevo-panel",
    "aliases": ["variante uno", "variante dos", "variante tres"],
    "desc": "Descripción para TTS y logs"
},

# Tipo B — nueva acción de subproceso
"mi_nueva_accion": {
    "action": {"type": "powershell", "run": "Get-Algo | Out-String"},
    "aliases": ["ejecutar algo", "hacer algo", "correr algo"],
    "desc": "Descripción amigable",
    "return_output": True,    # si DARIUS debe leer el resultado en voz
    "confirm": False          # True si la acción es destructiva/irreversible
},
```

Los aliases se normalizan automáticamente en `_build_table()` al importar el módulo. No es necesario incluir variantes con/sin tildes — la normalización las unifica.

---

*Documentación generada a partir del análisis estático de `main.py` (v6.x) y `windows_commands.py`. Para reportar inexactitudes o proponer mejoras, abrir un issue en el repositorio del proyecto.*

# Agent.md — Contexto Maestro para IA sobre Darius AI

> **Para cualquier IA o asistente de código que trabaje en este proyecto:**
> Lee este documento completo antes de proponer cualquier cambio. Contiene la
> arquitectura real del sistema, las decisiones de diseño ya tomadas y las
> reglas que debes respetar para no romper el comportamiento existente.
>
> Última actualización: Versión 7.0.0 — Disparador acústico por doble aplauso, gestión multi-monitor Win32, automatización de espacio de trabajo, motor ElevenLabs con caché SHA-256 en disco, arquitectura BYOK multi-proveedor, visualizador 60 FPS con NumPy, memoria en Obsidian — Septiembre 2026.

---

## 1. ¿Qué es Darius AI?

Darius AI es un **asistente de escritorio con voz para Windows**, construido
íntegramente en Python. Su propósito es ser el copiloto de Óscar en su PC:
ejecutar comandos del sistema operativo por voz, gestionar notas y diarios en
Obsidian, responder preguntas en lenguaje natural utilizando el proveedor de IA
configurado por el usuario (BYOK), y mantener un consumo mínimo de recursos (<90 MB RAM).

**Principios fundacionales (NO cambiarlos sin discusión):**

1. **Local-first:** La mayoría de comandos se resuelven sin internet y sin
   consumir cuota de API (abrir programas, paneles de control, volumen, diario local).
   La IA en la nube o local es complementaria, no el primer paso.
2. **BYOK (Bring Your Own Key) & Flexibilidad de Modelos:** El usuario puede
   escoger su motor preferido (Google Gemini, OpenAI / ChatGPT, Groq, NVIDIA NIM,
   OpenRouter, Ollama local o endpoints personalizados) y configurar sus claves
   desde la interfaz gráfica o archivos de entorno.
3. **Degradación elegante:** Si el proveedor principal falla por cuota (HTTP 429)
   o error de API, el sistema ejecuta un fallback defensivo hacia modelos de respaldo
   en OpenRouter o proporciona una respuesta verbal clara sin colapsar.
4. **Una sola instancia:** Mutex Win32 nativo garantiza que solo corra una copia en memoria.
5. **Sin dependencias ocultas:** Toda la configuración vive en `config.json`
   (parámetros y credenciales BYOK) y `.env` (variables de entorno). Nada hardcodeado.

---

## 2. Stack Tecnológico

| Capa | Tecnología | Motivo |
| :--- | :--- | :--- |
| **UI** | CustomTkinter + tkinter Canvas + NumPy | Tema oscuro Slate/Zinc nativo, soporte High-DPI, sin Electron |
| **Animación** | `HighPerfWaveVisualizer` (NumPy + Canvas) | 60 FPS, actualización atómica `coords()`, 0 flicker, 0 fugas de memoria |
| **Configuración GUI** | `BYOKSettingsModal` (`ctk.CTkToplevel`) | Gestión visual de proveedores, claves enmascaradas y ping en vivo |
| **Disparador Acústico** | `acoustic_trigger.py` (sounddevice + NumPy) | Detección de doble aplauso en tiempo real, filtro adaptativo de ruido y auto-sondeo de micrófono |
| **Voz entrada** | SpeechRecognition + PyAudio | Google STT (es-ES) con calibración de ruido ambiental |
| **Voz salida** | SAPI (`SpVoice`) + Edge-TTS + ElevenLabs | Síntesis nativa o neural en hilo COM desacoplado con caché SHA-256 en disco (`tts_cache.py`) |
| **Espacio de Trabajo** | `workspace_manager.py` (Win32 User32) | Multi-monitor geometry, window snapping, IDE focus nativo (`AttachThreadInput`), rutinas Darius/Dev/Trading |
| **Motor BYOK** | `ai_client.py` (Gemini SDK + OpenAI REST via `urllib`) | 7 proveedores soportados (Gemini, OpenAI, Groq, NIM, OpenRouter, Ollama, Custom) |
| **Memoria** | `obsidian_brain.py` (Markdown + YAML) | Persistencia privada y portable en la bóveda local de Obsidian |
| **SO Windows** | pywin32, subprocess, PowerShell, PyCAW, winreg | Control del sistema operativo con listas de argumentos (`shell=False`) |
| **Configuración** | `config_loader.py` (`config.json` + `.env`) | Merge jerárquico y validación de esquema con tipado fuerte |
| **Threading** | `threading` + `queue.Queue` | Manejo de colas COM para TTS y llamadas asíncronas de red |

---

## 3. Estructura de Archivos

```
Darius-AI/
├── .env                     <- Variables de entorno locales (GEMINI_API_KEY, ELEVENLABS_API_KEY...). Excluido de Git.
├── .env.example             <- Plantilla de credenciales sin secretos.
├── .gitignore               <- Excluye .env, *.log, cache, .vscode/, .venv/, audio_cache/, etc.
├── .github/
│   └── workflows/
│       └── main_darius-ai.yml  <- CI: Ruff + Pytest matrix (Win 3.11/3.12) + Gitleaks + Pip-audit
├── Agent.md                 <- ESTE ARCHIVO — Contexto maestro para IAs y desarrolladores
├── README.md                <- Documentación técnica pública y guía de inicio rápido
├── requirements.txt         <- Dependencias completas del entorno de ejecución en Windows
├── requirements-dev.txt     <- Dependencias para pruebas y linting (pytest, ruff, pytest-subtests)
├── pyproject.toml           <- Configuración de Ruff (line-length=120) y pytest
├── config.json              <- Parámetros de configuración, credenciales BYOK y rutinas de workspace
├── config_loader.py         <- Carga jerárquica de config.json con propiedades tipadas snake_case
├── main.py                  <- NÚCLEO — Interfaz CustomTkinter, visualizador 60 FPS, enrutador de comandos, telemetría
├── byok_settings.py         <- MODAL GUI — Configuración interactiva de proveedores LLM y prueba de latencia
├── acoustic_trigger.py      <- DISPARADOR ACÚSTICO — Detección de doble aplauso en streaming y auto-sondeo de micro
├── workspace_manager.py     <- ESPACIO DE TRABAJO — Multi-monitor Win32, snapping, IDE focus y rutinas de automatización
├── tts_cache.py             <- CACHÉ DE AUDIO — Almacenamiento WAV local con hash SHA-256 (texto+voz+modelo)
├── elevenlabs_tts_engine.py <- MOTOR TTS ELEVENLABS — Síntesis neural 24kHz con fallback streaming/REST
├── edge_tts_engine.py       <- MOTOR TTS EDGE — Síntesis neural Microsoft Edge
├── tts_worker.py            <- WORKER TTS — Despachador multi-motor (ElevenLabs > Edge > SAPI) desacoplado en hilo COM
├── ai_client.py             <- MOTOR BYOK — Clientes Gemini, OpenAI, Groq, NVIDIA NIM, OpenRouter, Ollama
├── obsidian_brain.py        <- CEREBRO — Gestión de notas diarias, memorias y búsqueda contextual en Obsidian
├── windows_commands.py      <- Catálogo de comandos del SO (_PS, _CMD, _MMC, _CONTROL, python actions)
├── human_gui.py            <- AUTOMATIZACIÓN GUI — Curvas de Bézier cúbicas, tipeo estocástico Unicode y scraper web nativo
├── agentic_bridge.py       <- PUENTE AGÉNTICO — Loop de ejecución de herramientas autónomas y fast-path CLI
├── voice_filter.py          <- Filtro y matching fonético de nombre en texto
├── stt_engine.py            <- Motor STT con soporte para calibración y backends
│
├── assets/                  <- Recursos gráficos oficiales (darius.ico, logo.png, logo_icon.png, logo_badge.png, social_preview.png, banner.png, generate_icon.py)
├── docs/                    <- Documentación y activos visuales web (favicon.png, social_preview.png, banner.png)
├── build_nuitka.py          <- SCRIPT DE COMPILACIÓN — Generación de binario nativo C standalone con Nuitka
├── installer.iss            <- SCRIPT DE INSTALADOR — Generador de setup Windows con Inno Setup
├── tests/
│   ├── conftest.py          <- Configuración de pytest y fixtures compartidos
│   ├── test_human_gui.py    <- Tests de trayectorias de Bézier, failsafe Win32 y scraper web
│   ├── test_agentic_bridge.py <- Tests del motor de herramientas autónomas y tool execution
│   ├── test_acoustic_trigger.py <- Tests de detección de aplausos, RMS mono y piso de ruido adaptativo
│   ├── test_workspace_manager.py <- Tests de geometría multi-monitor, snapping de ventanas y rutinas
│   ├── test_tts_cache.py    <- Tests de persistencia, hashing SHA-256 y atomicidad de caché WAV
│   ├── test_settings_tts.py <- Tests de persistencia y configuración GUI de TTS y ElevenLabs
│   ├── test_byok_providers.py  <- Tests del motor BYOK, resolución de claves y ping de conexión
│   ├── test_commands_v6.py  <- Tests de comandos del sistema operativo y rutas absolutas
│   ├── test_config_loader.py<- Tests de merge jerárquico y persistencia de configuración
│   ├── test_gemini_v6.py    <- Tests de integración y limpieza de Markdown para Gemini
│   ├── test_obsidian_brain.py <- Tests de persistencia de diario y memorias en Markdown/YAML
│   └── test_voice_v6.py     <- Tests del subsistema de audio, filtros fonéticos y serialización WAV
│
├── CHANGELOG.md             <- Registro cronológico de cambios y versiones
├── CONTRIBUTING.md          <- Guía de contribución y estándares de código
├── SECURITY.md              <- Políticas de seguridad y tratamiento de credenciales
│
├── darius.log               <- Log rotativo del sistema (%APPDATA%\DariusAI en frozen / local en dev)
├── chat_history.txt         <- Historial local de interacciones
├── apps_cache.json          <- Caché de aplicaciones instaladas en Windows
└── audio_cache/             <- Caché local en disco de audios sintetizados WAV (SHA-256)
```

---

## 4. Flujo de Datos Principal

```
USUARIO HABLA / ESCRIBE
        |
        v
[Modo PTT]   ─────────────────┐
[Modo NOMBRE] ────────────────┤  -> Google STT (es-ES)  ->  texto transcrito
[Modo AUTO]  ─────────────────┘
                                       |
                          process_recognized_text()
                            (filtro fonético por nombre)
                                       |
                               execute_command(cmd)
                                [limpia nombre del comando]
                                       |
                ┌──────────────────────┴────────────────────────┐
                │ ¿Coincide patrón local en _CMD_PATTERNS?       │ No
                v                                                v
         Handler local                                    ask_ai(cmd) (ai_client.py)
         (_cmd_hora, _cmd_abrir,                                 |
          _cmd_accion -> windows_commands.py,                    |-> Inyección de contexto
          _cmd_diario, _cmd_recordar -> obsidian_brain.py)       |   desde Obsidian Vault
                |                                                |
                v                                      ┌─────────┴──────────┐
            talk(respuesta)                            │ Proveedor Activo   │ Fallo de cuota / red
                |                                      │ (Gemini, OpenAI,   │
                v                                      │  Groq, NIM, Ollama)│
         tts_queue.put()                               v                    v
                |                                  respuesta            Fallback defensivo
         [tts-worker]                                  |              (OpenRouter rotativo)
       SAPI.SpVoice.Speak()                            └────────────────────┬───────────────┘
                                                                            |
                                                                     talk(respuesta)
```

---

## 5. Arquitectura del Motor BYOK (`ai_client.py`)

### 5.1 Proveedores Soportados y Configuración

El motor de IA implementa un despachador unificado que resuelve credenciales de forma jerárquica:
1. `config.json` (`llm.providers.<provider>.api_key`) — Modificado desde el modal de ajustes.
2. Variables de entorno (`.env` o variables del sistema).
3. Valores por defecto (URLs base oficiales y modelos estándar).

| Proveedor | Identificador | Base URL | Modelo Default | Mecanismo |
| :--- | :--- | :--- | :--- | :--- |
| **Google Gemini** | `gemini` | N/A (Google GenAI SDK) | `gemini-3.6-flash` | `genai.Client(api_key=...)` |
| **OpenAI** | `openai` | `https://api.openai.com/v1` | `gpt-4o-mini` | `_call_openai_compatible()` |
| **Groq** | `groq` | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` | `_call_openai_compatible()` |
| **NVIDIA NIM** | `nvidia_nim` | `https://integrate.api.nvidia.com/v1` | `meta/llama-3.3-70b-instruct` | `_call_openai_compatible()` |
| **OpenRouter** | `openrouter` | `https://openrouter.ai/api/v1` | `deepseek/deepseek-r1:free` | `_call_openai_compatible()` |
| **Ollama** | `ollama` | `http://localhost:11434/v1` | `llama3.2` | `_call_openai_compatible()` |
| **Personalizado** | `custom` | *Configurable por usuario* | *Configurable por usuario* | `_call_openai_compatible()` |

### 5.2 Llamador Universal OpenAI-Compatible (`_call_openai_compatible`)

- Implementado mediante la biblioteca estándar de Python (`urllib.request`), sin dependencias pesadas.
- Configuración de headers estándar (`Authorization: Bearer <KEY>`, `Content-Type: application/json`).
- Para **Ollama**, envía una clave ficticia `ollama` para satisfacer el protocolo sin requerir autenticación real.
- Parámetros: `temperature: 0.7`, `max_tokens: 800`.
- Timeout estricto de 30 segundos por llamada para evitar bloqueos del hilo de ejecución.

### 5.3 Diagnóstico y Prueba de Conexión (`test_provider_connection`)

Función asíncrona/diagnóstica que ejecuta una consulta mínima de 1 token (*"ping"*) hacia el endpoint configurado, midiendo la latencia de ida y vuelta:

```python
success, latency_ms, message = test_provider_connection(
    provider="groq",
    api_key="...",
    base_url="https://api.groq.com/openai/v1",
    model="llama-3.3-70b-versatile",
)
```

### 5.4 Inyección Contextual de Obsidian

Tanto en llamadas a Gemini como a los proveedores compatibles con OpenAI, `_build_system_instruction(prompt)` consulta la bóveda local (`obsidian_brain.get_memory_context(prompt)`) e inyecta notas relevantes en el bloque de instrucciones del sistema, garantizando continuidad cognitiva entre todos los modelos.

---

## 6. Decisiones Arquitectónicas Clave

### D1 — Motor BYOK Multi-Proveedor con compatibilidad OpenAI
**Decisión:** Centralizar todas las conexiones LLM en `ai_client.py` con una interfaz común y resolver credenciales desde `config.json` o `.env`. Esto permite al usuario cambiar de proveedor en un clic o usar modelos locales con Ollama sin recompilar ni alterar código.

### D2 — Visualizador Vectorial de 60 FPS con NumPy sobre Canvas
**Decisión:** Utilizar `numpy.sin()` para generar 3 capas de ondas sinusoidales armónicas con desfase continuo, pre-instanciar los objetos de línea en `tkinter.Canvas` y actualizar sus posiciones exclusivamente mediante `canvas.coords(line_id, *points)`. Se prohíbe el uso de `canvas.delete("all")` para evitar la recolección de basura continua y el parpadeo de pantalla.

### D3 — Modal de Ajustes GUI (`BYOKSettingsModal`)
**Decisión:** Un `ctk.CTkToplevel` modal con selector de proveedor, campos para modelo, URL base, clave de API oculta con botón de visibilidad (`👁`) y botón de prueba de conexión en tiempo real. Los cambios se persisten inmediatamente en `config.json` y se aplican en caliente.

### D4 — TTS en Hilo COM Separado con Cola de Mensajes
**Decisión:** `TTSWorker` corre en su propio hilo invocando `pythoncom.CoInitialize()` y consumiendo una `queue.Queue`. Esto evita que la síntesis de voz congele la interfaz gráfica o bloquee la captura de audio.

### D5 — Mutex Win32 para Instancia Única
**Decisión:** `win32event.CreateMutex` con identificador global. Si la aplicación ya está abierta, muestra un diálogo informativo y finaliza con `sys.exit(0)`, evitando colisiones de micrófono y archivos.

### D6 — Subprocesos con Rutas Completas y `shell=False`
**Decisión:** Todos los subprocesos de `windows_commands.py` utilizan `creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` y listas de argumentos validadas. Se prohíbe `shell=True` para eliminar riesgos de inyección de comandos.

### D7 — Memoria y Persistencia Local en Bóveda de Obsidian
**Decisión:** Las memorias, diarios y preferencias se guardan en la bóveda local de Obsidian en formato Markdown plano con frontmatter YAML (`obsidian_brain.py`), garantizando privacidad, portabilidad y propiedad total de los datos por parte del usuario.

### D8 — Calidad de Código Estricta con Ruff
**Decisión:** El pipeline de integración continua valida el 100% del código con `ruff check .` bajo límite de línea de 120 caracteres. No se permiten errores de linter en el repositorio.

### D9 — Disparador Acústico por Doble Aplauso con Piso de Ruido Adaptativo
**Decisión:** `AcousticDoubleClapDetector` analiza frames PCM de 50ms en streaming con `sounddevice` y `numpy`. Mantiene un piso de ruido adaptativo exponencial (`noise_floor = alpha * noise_floor + (1 - alpha) * rms`) con factor dinámico `multiplier * max(noise_floor, min_rms)`. Detecta 2 picos acústicos consecutivos dentro de una ventana temporal calibrada (120ms a 750ms) y ejecuta auto-sondeo de micrófonos (`probe_best_input_device`) si el dispositivo predeterminado está mudo (RMS < 0.001).

### D10 — Gestión Multi-Monitor Nativa Win32 y Rutinas de Espacio de Trabajo
**Decisión:** `WorkspaceManager` utiliza `EnumDisplayMonitors` y `GetMonitorInfoW` de Win32 para mapear coordenadas reales de múltiples pantallas. Permite colocar ventanas en monitores específicos mediante `SetWindowPos` y enfocar instancias existentes de IDEs (`Cursor.exe`, `Code.exe`) usando `AttachThreadInput` y `SetForegroundWindow` para evitar la creación de procesos duplicados. Automatiza rutinas de bienvenida ("Protocolo Darius"), modo desarrollo y modo trading.

### D11 — Caché de Audio en Disco con Hash SHA-256 (`TTSDiskCache`)
**Decisión:** Almacenar respuestas de voz sintetizadas en `audio_cache/` indexadas por hash SHA-256 truncado a 24 caracteres de la tupla normalizada `(text|voice|model|format)`. Frases recurrentes de estado y saludos ("Buenos días, Óscar", "Protocolo Darius activado", "Monitores listos") se reproducen al instante (0 ms de latencia) y con 0 consumo de cuota de API en ElevenLabs.

### D12 — Compilación Nativa C Standalone con Nuitka e Instalador Inno Setup
**Decisión:** Compilar la aplicación a binario nativo de Windows mediante **Nuitka** (`build_nuitka.py`) con plugins de CustomTkinter y SoundDevice, generando un ejecutable optimizado que elimina falsos positivos en antivirus (Windows Defender) y arranca en milisegundos. Para aislar los datos mutables del usuario, `config_loader.get_user_data_dir()` redirige la persistencia (`config.json`, logs, cachés) a `%APPDATA%\DariusAI` en modo congelado (`sys.frozen`), protegiendo la carpeta de instalación de bloqueos de permisos de UAC. El instalador con **Inno Setup** (`installer.iss`) instala en `{localappdata}\Programs\DariusAI` sin requerir elevación de administrador.

### D13 — Modal Gráfico Dual (LLM + TTS/ElevenLabs) con Prueba en Vivo
**Decisión:** Integrar toda la configuración de motores de síntesis vocal (SAPI5, Edge-TTS, ElevenLabs) directamente en la interfaz gráfica (`byok_settings.py`), incluyendo clave de API enmascarada, selector de Voice ID, modelo neural, alternador de caché y botón de prueba auditiva en vivo (`🔊 PROBAR VOZ`). Los usuarios nunca necesitan manipular archivos `.env` ni editar JSON manualmente.

### D14 — Cliente REST Nativo Zero-Overhead para Motores de IA
**Decisión:** Conectar a Google Gemini, OpenAI, Groq, NVIDIA, OpenRouter y Ollama mediante llamadas HTTP/REST puras con `urllib.request` y `requests`, evitando SDKs monolíticos pesados (como `google-genai`) que autogeneran más de 160.000 líneas de modelos Pydantic y saturan el compilador C++ de Nuitka. Esto reduce el tiempo de compilación nativa a menos de 3 minutos y optimiza el consumo de RAM a <90 MB.

### D15 — Motor Autónomo Agentic Bridge y Fast-Path Router para Herramientas Locales
**Decisión:** Dotar a Darius AI de capacidad de acción autónoma mediante `agentic_bridge.py` y un protocolo de Tool Calling agnóstico del proveedor (`[ACTION: tool_name(args)]`).
1. **Fast-Path Router Local (0 ms):** Enrutamiento por expresiones regulares en `main.py` y `windows_commands.py` para comandos frecuentes de red (`ipconfig /flushdns`, renovación de IP), utilidades de desarrollador (`gh pr list`, `git status`) y diagnósticos de RAM (`Get-Process`).
2. **Autonomous Tool Loop Multi-Proveedor:** Los modelos LLM (Gemini, OpenAI, Groq, OpenRouter, Ollama) pueden invocar herramientas del sistema operativo o CLIs activos emitiendo la etiqueta estructurada de acción. Darius intercepta la llamada, ejecuta el binario local herméticamente con timeout de 8-10s y reinyecta la salida de consola al modelo para que sintetice una respuesta verbal ejecutiva.
3. **Protocolo de Confirmación para Acciones Destructivas:** Las operaciones de solo lectura y diagnóstico se ejecutan de inmediato sin fricción; las operaciones modificadoras o destructivas (merges de PRs, borrado de archivos, reseteos forzados) activan un diálogo de confirmación por voz antes de proceder.

### D16 — Automatización de GUI Antropomórfica ("Computer Use") y Web Scraper Zero-Dependency
**Decisión:** Implementar automatización del cursor del mouse, clics, hotkeys, digitación de teclado y extracción de páginas web mediante `human_gui.py` usando exclusivamente la Win32 API (`ctypes.windll.user32`) y la librería estándar (`urllib.request`, `html.parser`), sin dependencias pesadas ni binarios de terceros (evitando `pyautogui`, `selenium`, `playwright`).
1. **Trayectorias de Bézier Cúbicas y Física Fitts:** Los desplazamientos del cursor calculan puntos de control estocásticos ortogonales y aplican perfiles de aceleración/desaceleración senoidales (*Ease-in / Ease-out*), añadiendo micro-jitter de 1-2px para emular fielmente el movimiento neuromuscular humano.
2. **Digitación con Distribución Gaussiana y Soporte Unicode:** El tipeo utiliza pausas de variabilidad natural estocástica (WPM dinámico) e inyecta eventos `KEYEVENTF_UNICODE` (`0x0004`), garantizando la escritura universal de caracteres acentuados, eñes y caracteres especiales con total independencia del layout del teclado físico.
3. **Mecanismo de Failsafe de Emergencia:** Se evalúa de manera atómica antes de cada sub-paso de movimiento o pulsación de tecla el cursor en la esquina superior izquierda `(0, 0)` o la bandera de interrupción activada por comando de voz (*"Darius, detente"*), abortando inmediatamente cualquier automatización activa y previniendo bucles incontrolados.
4. **Scraper Web Resiliente Zero-Dependency:** Extracción de DOM y texto legible con sanitización de scripts, estilos, comentarios y entidades HTML mediante un parser SAX (`HTMLTextExtractor`) y fallback de expresiones regulares, operando de forma hermética con timeout de 10 segundos y User-Agent de navegador moderno.

---

## 7. Modos de Activación de Voz y Eventos

- **Disparador Acústico (Doble Aplauso):**
  - Hilo de escucha en streaming continuo en segundo plano (`sounddevice.InputStream`).
  - Al detectar 2 aplausos sucesivos en la ventana de 120-750 ms, despierta al asistente y activa el modo de escucha STT automáticamente.
- **Modo PTT (Push-to-Talk):**
  - Mantiene presionada la tecla configurada (`LISTEN_KEY`, por defecto `right ctrl`).
  - Graba audio continuamente en memoria y lo envía a STT al soltar la tecla.
  - Cero falsos positivos; recomendado para entornos ruidosos.
- **Modo NOMBRE:**
  - Monitorea el audio en segundo plano y analiza el texto transcrito con `voice_filter.check_name_in_text()`.
  - Utiliza comparación fonética difusa (`SequenceMatcher`) con umbral configurable (`NAME_SIMILARITY_CUTOFF = 0.60`).
  - Al detectar el nombre ("Darius"), procesa el resto de la frase como comando.
- **Modo AUTO:**
  - Escucha continua que procesa de inmediato cualquier frase capturada.
  - Si coincide con un comando del sistema o de Obsidian, lo ejecuta localmente; de lo contrario, lo envía al motor de IA activo.

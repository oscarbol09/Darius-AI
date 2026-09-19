# Agent.md — Contexto Maestro para IA sobre Darius AI

> **Para cualquier IA o asistente de código que trabaje en este proyecto:**
> Lee este documento completo antes de proponer cualquier cambio. Contiene la
> arquitectura real del sistema, las decisiones de diseño ya tomadas y las
> reglas que debes respetar para no romper el comportamiento existente.
>
> Última actualización: Versión 6.6.0 — Arquitectura BYOK multi-proveedor, visualizador 60 FPS con NumPy, modal de configuración GUI, memoria en Obsidian — Septiembre 2026.

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
| **Voz entrada** | SpeechRecognition + PyAudio | Google STT (es-ES) con calibración de ruido ambiental |
| **Voz salida** | SAPI vía win32com (`SpVoice`) + Edge-TTS | Síntesis nativa sin latencia en hilo COM desacoplado |
| **Motor BYOK** | `ai_client.py` (Gemini SDK + OpenAI REST via `urllib`) | 7 proveedores soportados (Gemini, OpenAI, Groq, NIM, OpenRouter, Ollama, Custom) |
| **Memoria** | `obsidian_brain.py` (Markdown + YAML) | Persistencia privada y portable en la bóveda local de Obsidian |
| **SO Windows** | pywin32, subprocess, PowerShell, PyCAW, winreg | Control del sistema operativo con listas de argumentos (`shell=False`) |
| **Configuración** | `config_loader.py` (`config.json` + `.env`) | Merge jerárquico y validación de esquema con tipado fuerte |
| **Threading** | `threading` + `queue.Queue` | Manejo de colas COM para TTS y llamadas asíncronas de red |

---

## 3. Estructura de Archivos

```
Darius-AI/
├── .env                     <- Variables de entorno locales (GEMINI_API_KEY, OPENAI_API_KEY...). Excluido de Git.
├── .env.example             <- Plantilla de credenciales sin secretos.
├── .gitignore               <- Excluye .env, *.log, cache, .vscode/, .venv/, etc.
├── .github/
│   └── workflows/
│       └── main_darius-ai.yml  <- CI: Ruff + Pytest matrix (Win 3.11/3.12) + Gitleaks + Pip-audit
├── Agent.md                 <- ESTE ARCHIVO — Contexto maestro para IAs y desarrolladores
├── README.md                <- Documentación técnica pública y guía de inicio rápido
├── requirements.txt         <- Dependencias completas del entorno de ejecución en Windows
├── requirements-dev.txt     <- Dependencias para pruebas y linting (pytest, ruff, pytest-subtests)
├── pyproject.toml           <- Configuración de Ruff (line-length=120) y pytest
├── config.json              <- Parámetros de configuración y credenciales BYOK locales
├── config_loader.py         <- Carga jerárquica de config.json con propiedades tipadas snake_case
├── main.py                  <- NÚCLEO — Interfaz CustomTkinter, visualizador 60 FPS, enrutador de comandos
├── byok_settings.py         <- MODAL GUI — Configuración interactiva de proveedores LLM y prueba de latencia
├── ai_client.py             <- MOTOR BYOK — Clientes Gemini, OpenAI, Groq, NVIDIA NIM, OpenRouter, Ollama
├── obsidian_brain.py        <- CEREBRO — Gestión de notas diarias, memorias y búsqueda contextual en Obsidian
├── windows_commands.py      <- Catálogo de comandos del SO (_PS, _CMD, _MMC, _CONTROL con rutas completas)
├── voice_filter.py          <- Filtro y matching fonético de nombre en texto
├── tts_worker.py            <- Worker TTS (SAPI COM) desacoplado en hilo propio con cola de mensajes
├── edge_tts_engine.py       <- Motor TTS alternativo de alta fidelidad con Edge-TTS
├── stt_engine.py            <- Motor STT con soporte para calibración y backends
│
├── tests/
│   ├── conftest.py          <- Configuración de pytest y fixtures compartidos
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
├── darius.log               <- Log rotativo del sistema (excluido de Git)
├── chat_history.txt         <- Historial local de interacciones (excluido de Git)
└── apps_cache.json          <- Caché de aplicaciones instaladas en Windows (excluido de Git)
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

---

## 7. Modos de Activación de Voz

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

# Changelog

## [7.0.0] - 2026-09-19 — Workspace & Acoustic Automation Edition

### Agregado
- **Detector Acústico de Doble Aplauso (`acoustic_trigger.py`):**
  - Detección en tiempo real de transitorios acústicos rápidos y dobles aplausos con adaptación continua del suelo de ruido (`NOISE_FLOOR_ALPHA=0.992`).
  - Activación automática de rutinas de trabajo compuestas o despertar del asistente sin interactuar con el teclado.
  - Sondeo y auto-selección inteligente de micrófonos para evitar bloqueos por dispositivos mudos o desconectados.
- **Gestión Avanzada de Workspaces y Multi-Monitor Win32 (`workspace_manager.py`):**
  - Detección y ordenación de monitores físicos conectados (`EnumDisplayMonitors`).
  - Snap automático y apertura dirigida de navegadores y dashboards a pantallas secundarias específicas.
  - Enfoque nativo de instancias activas de Cursor IDE y VS Code (`QueryFullProcessImageNameW` + `AttachThreadInput`), evitando la duplicación de procesos y con alternancia a pantalla completa (F11).
  - Orquestación de rutinas automáticas: *Protocolo Darius*, *Modo Desarrollo*, *Modo Trading* y *Modo Concentración*.
- **Motor TTS ElevenLabs con Caché Local Zero-Latency (`elevenlabs_tts_engine.py` & `tts_cache.py`):**
  - Síntesis de voz ultra-realista con modelos multilingües de ElevenLabs y streaming de audio PCM a 24 kHz.
  - Sistema de almacenamiento en disco con hashes SHA-256 (`audio_cache/`) para reproducir frases recurrentes con 0ms de latencia de red y 0 consumo de tokens de API.
- **Nuevos Comandos de Voz y UI:**
  - Nuevos patrones de voz en `windows_commands.py`: "iniciar protocolo darius", "modo desarrollo", "modo trading", "enfocar cursor", "ver monitores".
  - Nuevos indicadores de telemetría en la interfaz gráfica: Badges de Monitores, Toggle interactivo de Doble Aplauso y Motor TTS activo.
- **Suites de Pruebas Unitarias:**
  - `tests/test_acoustic_trigger.py`: Pruebas de RMS, resolución de dispositivos y ciclo de vida.
  - `tests/test_workspace_manager.py`: Pruebas de detección de monitores, snapping y rutinas compuestas.
  - `tests/test_tts_cache.py`: Pruebas de hashing SHA-256 determinista y guardado/reproducción WAV.

## [6.6.0] - 2026-09-19

### Agregado
- **Motor BYOK (*Bring Your Own Key*) Multi-Proveedor (`ai_client.py`):**
  - Soporte para 7 proveedores de IA: Google Gemini, OpenAI / ChatGPT, OpenRouter, NVIDIA NIM, Groq Cloud, Ollama (ejecución local en `http://localhost:11434/v1`) y endpoints compatibles con OpenAI.
  - Llamador universal `_call_openai_compatible()` implementado sobre la biblioteca estándar `urllib`, sin dependencias externas pesadas.
  - Función de diagnóstico `test_provider_connection()` con prueba de latencia en vivo y verificación de estado.
  - Resolución jerárquica de claves y parámetros: `config.json` (ajustes de usuario) > `.env` (variables de entorno) > defaults.
- **Modal Gráfico de Configuración BYOK (`byok_settings.py`):**
  - Ventana interactiva `BYOKSettingsModal` (`ctk.CTkToplevel`) accesible desde el botón `⚙ Configuración` de la barra superior.
  - Selector de proveedor activo, catálogo de modelos recomendados con entrada libre, configuración de URL base y campo de clave de API enmascarada con alternador de visibilidad.
  - Herramienta de prueba de conexión en tiempo real con indicador visual y reporte de latencia en milisegundos.
- **Visualizador Vectorial de Audio a 60 FPS (`HighPerfWaveVisualizer` en `main.py`):**
  - Generación de 3 capas de ondas sinusoidales armónicas con desfase continuo aceleradas con **NumPy** sobre `tkinter.Canvas`.
  - Actualización atómica de coordenadas mediante `canvas.coords()` que prescinde de `delete("all")`, eliminando el parpadeo de pantalla y las pausas por recolección de basura.
  - Habilitación de escalado High-DPI en Windows (`enable_dpi_awareness`).
- **Suite de Pruebas del Motor BYOK (`tests/test_byok_providers.py`):**
  - 16 pruebas unitarias e integración que cubren la resolución de credenciales, emulación de llamadas compatibles con OpenAI, clasificación de errores y pruebas de conexión simuladas.

### Mejorado
- Rediseño de la interfaz gráfica aplicando la paleta Slate/Zinc (`#09090b`, `#27272a`, `#3b82f6`) con mayor contraste y legibilidad.
- Inyección de contexto de la bóveda de Obsidian estandarizada para todos los proveedores de IA.
- Sincronización completa de la documentación técnica y especificaciones de arquitectura.

## [6.5.0] - 2026-09-19

### Agregado
- Módulo `obsidian_brain.py` para integración directa de memoria y notas en Obsidian Vault (Markdown + YAML frontmatter).
- Comandos por voz para inserción en diario personal (`Diario/YYYY-MM-DD.md`) y guardado de memorias persistentes.
- Inyección contextual de notas de Obsidian en el prompt del sistema de Google Gemini.
- Suite de pruebas unitarias para el motor de Obsidian (`test_obsidian_brain.py`).

### Eliminado
- Eliminación total de dependencias y código de Supabase (`supabase_client.py`, `test_supabase_client.py`).
- Persistencia de configuración y caché 100% local en disco.

## [6.4.0] - 2026-09-19

### Cambios
- Transición a arquitectura 100% nativa de escritorio para Windows.
- Eliminación de dependencias y componentes web/Linux (`app.py`, `Dockerfile`, Railway).
- Consolidación de dependencias en un único `requirements.txt` optimizado para Windows.
- Actualización de metadatos del proyecto y documentación técnica.

## [6.3.0] - 2026-07-21

### Corregido
- Rotación automática de `chat_history.txt` (máx 10.000 líneas, poda al 80% del límite).
- TTL de `apps_cache.json` ahora usa UTC consistente en toda la app.
- Race condition en `_pending_action` protegida con `threading.RLock()`.
- `GEMINI_MAX_TOKENS` sincronizado entre `config_loader.py` (default 800) y tests.

### Agregado
- Indicador de progreso en escaneo de aplicaciones (`rglob("*.exe")`).
- `Dockerfile` multi-etapa para Railway.
- Tests unitarios para `config_loader.py`.
- Test de verificación de patrones `_CMD_PATTERNS` vs `test_commands_v6.py`.
- `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`.

### Mejorado
- CI/CD: Ruff + pytest + coverage + gitleaks + pip-audit.

## [6.2.0] - 2026-06

### Corregido
- Subprocess `shell=True` reemplazado por listas de args (5 ocurrencias).
- `os.system()` reemplazado por `subprocess.run()`.
- Defaults duplicados entre `app.py` y `config_loader.py` eliminados.

### Agregado
- `pyproject.toml` con Ruff, pytest, y pytest-cov.
- `requirements-dev.txt`.
- Validación de tipos en schema de `config.json`.
- Tests organizados en `tests/` con `conftest.py` + markers de plataforma.

### Refactorizado
- `main.py` → extraídos `ai_client.py` + `tts_worker.py` (210 líneas menos).

## [6.1.0] - 2026-05

### Corregido
- BUG 1: cutoff fuzzy subido (0.52→0.75) en `windows_commands.py`.
- BUG 2: `execute_command` limpia nombre antes de evaluar patrones.
- BUG 3: regex de apagar/reiniciar ampliados.
- BUG 4: `_cmd_accion` ya no captura preguntas genéricas.

## [6.0.0] - 2026-04

### Agregado
- Modos de activación PTT / NOMBRE / AUTO.
- Selector de modo en UI + indicador visual.
- `windows_commands.py` con fuzzy matching semántico.

### Cambios
- UI migrada de Tkinter a CustomTkinter.
- TTS worker en hilo separado.
- Single-instance mutex con win32event.

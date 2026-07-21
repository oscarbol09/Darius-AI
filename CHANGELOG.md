# Changelog

## [6.3.0] - 2026-07-21

### Corregido
- Rotación automática de `chat_history.txt` (máx 10.000 líneas, poda al 80% del límite)
- TTL de `apps_cache.json` ahora usa UTC consistente en toda la app
- Race condition en `_pending_action` protegida con `threading.RLock()`
- `GEMINI_MAX_TOKENS` sincronizado entre `config_loader.py` (default 800) y tests

### Agregado
- Indicador de progreso en escaneo de aplicaciones (`rglob("*.exe")`)
- `Dockerfile` multi-etapa para Railway/Azure
- Tests unitarios para `supabase_client.py` y `config_loader.py`
- Test de verificación de patrones `_CMD_PATTERNS` vs `test_commands_v6.py`
- `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`

### Mejorado
- CI/CD: Ruff + pytest + coverage + gitleaks + pip-audit

## [6.2.0] - 2026-06

### Corregido
- Subprocess `shell=True` reemplazado por listas de args (5 ocurrencias)
- `os.system()` reemplazado por `subprocess.run()`
- Defaults duplicados entre `app.py` y `config_loader.py` eliminados

### Agregado
- `pyproject.toml` con Ruff, pytest, y pytest-cov
- `requirements-dev.txt`
- Validación de tipos en schema de `config.json`
- Tests organizados en `tests/` con `conftest.py` + markers de plataforma

### Refactorizado
- `main.py` → extraídos `ai_client.py` + `tts_worker.py` (210 líneas menos)

## [6.1.0] - 2026-05

### Corregido
- BUG 1: cutoff fuzzy subido (0.52→0.75) en `windows_commands.py`
- BUG 2: `execute_command` limpia nombre antes de evaluar patrones
- BUG 3: regex de apagar/reiniciar ampliados
- BUG 4: `_cmd_accion` ya no captura preguntas genéricas

## [6.0.0] - 2026-04

### Agregado
- Modos de activación PTT / NOMBRE / AUTO
- Selector de modo en UI + indicador visual
- `windows_commands.py` con fuzzy matching semántico
- Integración con Supabase (chat_history, apps_cache, config compartida)

### Cambios
- UI migrada de Tkinter a CustomTkinter
- TTS worker en hilo separado
- Single-instance mutex con win32event

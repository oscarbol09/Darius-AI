<p align="center">
  🇺🇸 <b>English Summary</b> &nbsp;|&nbsp; 📜 Detailed Bilingual Audit Ledger Below
</p>

# 📋 Technical Audit & GitHub Issues Backlog — DARIUS AI v8.5
## Engineering & Quality Governance (`antigravity-ecc` / ECC Protocol)

> **Repository:** [`oscarbol09/Darius-AI`](https://github.com/oscarbol09/Darius-AI)  
> **Audited Release:** `v8.5.0` (Cybernetic Bento HUD + Dual-Language i18n)  
> **Status:** 12 of 17 audited issues closed in commits `0b92c7b..aa1b2cb`; 5 architectural & security issues remain open with `help wanted`.

---

# 📋 BACKLOG DE ISSUES TÉCNICOS: DARIUS AI v8.5
## Protocolo ECC (Engineering & Quality Governance) — Auditoría de Código y Arquitectura

> **Repositorio**: `oscarbol09/Darius-AI`  
> **Versión Auditada**: v8.5.0 (Cybernetic Bento)  
> **Fecha**: 14 de Noviembre de 2026  
> **Protocolo**: ECC Core Governance (`antigravity-ecc`), TDD & Verification Loop  
> **Estado**: Listo para publicación en GitHub Issues  

---

## 📊 RESUMEN EJECUTIVO DEL ESTADO DEL REPOSITORIO

| Categoría | Crítica 🔴 | Alta 🟠 | Media 🟡 | Baja 🔵 | Total |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Bugs en Código y Contratos** | 2 | 1 | 2 | 0 | **5** |
| **Seguridad y Sandbox** | 0 | 2 | 1 | 0 | **3** |
| **Arquitectura y Deuda Técnica** | 0 | 2 | 1 | 1 | **4** |
| **CI / CD y Pruebas** | 0 | 1 | 1 | 0 | **2** |
| **Release, Empaquetado y UI** | 0 | 0 | 0 | 3 | **3** |
| **TOTAL** | **2** | **6** | **5** | **4** | **17** |

---

## 📑 ÍNDICE DE ISSUES PUBLICADOS EN GITHUB

1. [#1 [BUG] Incompatibilidad de contrato en _cmd_scrape_web causa fallo permanente con 'Error al analizar la página: None'](https://github.com/oscarbol09/Darius-AI/issues/1) — `bug`, `help wanted`, `good first issue`
2. [#2 [BUG] TypeError silencioso en hilo trabajador de _cmd_human_click por argumento no soportado 'clicks'](https://github.com/oscarbol09/Darius-AI/issues/2) — `bug`, `help wanted`, `good first issue`
3. [#3 [BUG] Falla ejecución de atajos multi-tecla (ej. 'ctrl+c') en AgentPlanner por ausencia de tokenización](https://github.com/oscarbol09/Darius-AI/issues/3) — `bug`, `help wanted`, `good first issue`
4. [#4 [SECURITY] SafeCodeInterpreter vulnerable a agotamiento de memoria (DoS) y evasión mediante str.format()](https://github.com/oscarbol09/Darius-AI/issues/4) — `security`, `help wanted`
5. [#5 [SECURITY] Almacenamiento en texto plano de claves de API de LLM y TTS en config.json](https://github.com/oscarbol09/Darius-AI/issues/5) — `enhancement`, `help wanted`, `security`
6. [#6 [BUG/SECURITY] Regla de elevenlabs_key en CredentialStripper ofusca hashes MD5 legítimos y UUIDs](https://github.com/oscarbol09/Darius-AI/issues/6) — `bug`, `help wanted`, `security`
7. [#7 [BUG] Falla de Barge-In en EdgeTTS al reproducir audio mediante Win32 MCI bloqueante](https://github.com/oscarbol09/Darius-AI/issues/7) — `bug`, `help wanted`
8. [#8 [ARCH] Desacoplar clase monolítica DariusFinal en app.py (2,567 líneas)](https://github.com/oscarbol09/Darius-AI/issues/8) — `help wanted`, `refactor`
9. [#9 [ARCH] Migrar imports internos residuales de gui.human_gui a automation.human_input](https://github.com/oscarbol09/Darius-AI/issues/9) — `help wanted`, `good first issue`, `refactor`
10. [#10 [BUG] Dependencia no declarada 'soundfile' en requirements.txt para fallback de audio](https://github.com/oscarbol09/Darius-AI/issues/10) — `bug`, `help wanted`, `good first issue`
11. [#11 [TESTS] Salto silencioso de TestPatternsMatchMain en tests/test_commands_v6.py](https://github.com/oscarbol09/Darius-AI/issues/11) — `help wanted`, `good first issue`, `testing`
12. [#12 [CONCURRENCY] Condición de carrera en conversation_history por accesos multi-hilo concurrentes](https://github.com/oscarbol09/Darius-AI/issues/12) — `bug`, `help wanted`
13. [#13 [PORTABILITY] Rutas de proyectos locales hardcodeadas para el usuario 'Oscar' en ai_client.py](https://github.com/oscarbol09/Darius-AI/issues/13) — `enhancement`, `help wanted`, `good first issue`
14. [#14 [RELEASE] Sincronizar versión v8.5.0 en build_nuitka.py, installer.iss y release.yml](https://github.com/oscarbol09/Darius-AI/issues/14) — `documentation`, `help wanted`, `good first issue`
15. [#15 [PERF] Ejecución síncrona de psutil.disk_usage en el hilo principal de Tkinter](https://github.com/oscarbol09/Darius-AI/issues/15) — `help wanted`, `performance`
16. [#16 [UI/TOKENS] Reemplazar colores hexadecimales hardcodeados en byok_settings.py por tokens de gui_theme](https://github.com/oscarbol09/Darius-AI/issues/16) — `enhancement`, `help wanted`, `good first issue`
17. [#17 [CI/CD] Ruptura del Gate 1 de CI: 20 violaciones de Ruff bloquean integración continua](https://github.com/oscarbol09/Darius-AI/issues/17) — `help wanted`, `good first issue`, `testing`, `ci/cd`

---

# 🔴 BLOQUE 1: BUGS CRÍTICOS Y FALLOS EN TIEMPO DE EJECUCIÓN

---

### ISSUE #1: [BUG] Incompatibilidad de contrato en `_cmd_scrape_web` causa fallo permanente con `"Error al analizar la página: None"`

- **Título**: `[BUG] Incompatibilidad de contrato en _cmd_scrape_web causa fallo permanente con 'Error al analizar la página: None'`
- **Etiquetas**: `bug`, `critical`, `commands`
- **Prioridad**: Crítica
- **Módulos**: `src/darius_ai/gui/app.py`, `src/darius_ai/automation/human_input.py`

#### Descripción
Al solicitar a Darius analizar una página web (ej. *"Darius analiza la página https://example.com"*), el asistente descarga y procesa el HTML correctamente, pero de inmediato responde con un mensaje de error verbal:  
`"Error al analizar la página: None"` y no genera el resumen solicitado.

#### Causa Raíz
En `src/darius_ai/gui/app.py:2128-2130`:
```python
res = gui.scrape_web_content(url)
if not res.get("ok"):
    self.talk(f"Error al analizar la página: {res.get('error')}")
    return
```
Sin embargo, `HumanGUIAutomator.scrape_web_content()` en `src/darius_ai/automation/human_input.py:426-431` devuelve:
```python
return {
    "success": True,
    "url": clean_url,
    "title": title,
    "content": compact_text or "Página vacía o sin contenido legible.",
}
```
El diccionario contiene la clave `"success"`, no `"ok"`. En consecuencia, `res.get("ok")` retorna `None`, `not None` evalúa a `True`, y el método aborta siempre mostrando `error: None`.

#### Pasos para Reproducir
1. Ejecutar Darius AI.
2. Escribir o hablar: `"analiza la web https://docs.python.org"`.
3. Observar que el log indica éxito en la descarga pero la alocución vocal dice `"Error al analizar la página: None"`.

#### Solución Propuesta
En `src/darius_ai/gui/app.py`:
```python
# Línea 2126: migrar import deprecado
from src.darius_ai.automation.human_input import gui

res = gui.scrape_web_content(url)
if not (res.get("success") or res.get("ok")):
    self.talk(f"Error al analizar la página: {res.get('error', 'Fallo desconocido')}")
    return
```

#### Criterios de Aceptación (DoD)
- [ ] La verificación de estado comprueba `res.get("success")`.
- [ ] La consulta de scraping completa exitosamente y envía el prompt de resumen al LLM (`self.ask_gemini(...)`).
- [ ] Test unitario verificando la integración entre `app._cmd_scrape_web` y `gui.scrape_web_content`.

---

### ISSUE #2: [BUG] `TypeError` silencioso en hilo trabajador de `_cmd_human_click` por argumento no soportado `'clicks'`

- **Título**: `[BUG] TypeError silencioso en hilo trabajador de _cmd_human_click por argumento no soportado 'clicks'`
- **Etiquetas**: `bug`, `critical`, `automation`
- **Prioridad**: Crítica
- **Módulos**: `src/darius_ai/gui/app.py`, `src/darius_ai/automation/human_input.py`

#### Descripción
Al solicitar a Darius simular un clic de ratón (ej. *"haz clic"* o *"haz doble clic"*), el asistente responde vocalmente *"Haciendo clic en dos segundos"*, pero tras la espera no se realiza ningún clic. En la consola o logs se produce un fallo silencioso en el hilo `human-click`.

#### Causa Raíz
En `src/darius_ai/gui/app.py:2101-2115`:
```python
def _cmd_human_click(self, cmd: str):
    is_right = bool(re.search(r"derecho", cmd, re.IGNORECASE))
    is_double = bool(re.search(r"doble", cmd, re.IGNORECASE))
    clicks = 2 if is_double else 1
    button = "right" if is_right else "left"
    self.talk("Haciendo clic en dos segundos.")

    def run():
        time.sleep(2.0)
        from src.darius_ai.gui.human_gui import gui

        gui.human_click(button=button, clicks=clicks)  # <-- ERROR: parámetro no existe
        self.talk("Clic ejecutado.")

    threading.Thread(target=run, daemon=True, name="human-click").start()
```
La signatura real de `HumanGUIAutomator.human_click` en `src/darius_ai/automation/human_input.py:232` es:
```python
def human_click(
    self,
    x: int | None = None,
    y: int | None = None,
    button: str = "left",
    double: bool = False,
) -> bool:
```
El parámetro `clicks` no existe. Python lanza:
`TypeError: HumanGUIAutomator.human_click() got an unexpected keyword argument 'clicks'`.

#### Pasos para Reproducir
1. Ejecutar en terminal:  
   `python -c "from src.darius_ai.automation.human_input import gui; gui.human_click(button='left', clicks=1)"`
2. Verificar el stacktrace con `TypeError`.

#### Solución Propuesta
En `src/darius_ai/gui/app.py`:
```python
def _cmd_human_click(self, cmd: str):
    is_right = bool(re.search(r"derecho", cmd, re.IGNORECASE))
    is_double = bool(re.search(r"doble", cmd, re.IGNORECASE))
    button = "right" if is_right else "left"
    self.talk("Haciendo clic en dos segundos.")

    def run():
        time.sleep(2.0)
        from src.darius_ai.automation.human_input import gui

        gui.human_click(button=button, double=is_double)
        self.talk("Clic ejecutado.")

    threading.Thread(target=run, daemon=True, name="human-click").start()
```

#### Criterios de Aceptación (DoD)
- [ ] `gui.human_click` recibe `double=is_double` en lugar de `clicks`.
- [ ] La acción ejecuta sin excepciones tanto para clic simple como doble clic.
- [ ] Test automatizado validando la invocación de `_cmd_human_click`.

---

### ISSUE #3: [BUG] Falla ejecución de atajos multi-tecla (ej. `'ctrl+c'`) en `AgentPlanner` por ausencia de tokenización de teclas

- **Título**: `[BUG] Falla ejecución de atajos multi-tecla (ej. 'ctrl+c') en AgentPlanner por ausencia de tokenización`
- **Etiquetas**: `bug`, `high`, `agents`
- **Prioridad**: Alta
- **Módulos**: `src/darius_ai/core/agent_planner.py`, `src/darius_ai/automation/human_input.py`

#### Descripción
Cuando el planificador agéntico `AgentPlanner` descompone una tarea que incluye presionar combinaciones de teclas (ej. copiar texto con `ctrl+c` o pegar con `ctrl+v`), el paso reporta éxito pero ninguna tecla es presionada físicamente en el sistema operativo.

#### Causa Raíz
En `src/darius_ai/core/agent_planner.py:378-381`:
```python
elif action == "hotkey":
    keys = p.get("keys", "enter")
    gui.human_hotkey(keys)
    return True, f"Atajo ejecutado: {keys}"
```
`HumanGUIAutomator.human_hotkey(*keys: str)` espera una lista de argumentos posicionales (ej. `"ctrl"`, `"c"`).  
Al invocar `gui.human_hotkey("ctrl+c")`, el método busca `"ctrl+c"` en su diccionario de Virtual Keycodes (`VK_MAP`), no encuentra coincidencia y no envía eventos a Win32 `SendInput`.

En contraste, `agentic_bridge.py:278` implementa correctamente la tokenización:
```python
key_list = [k.strip() for k in re.split(r"[,+\s]+", keys) if k.strip()]
gui.human_hotkey(*key_list)
```

#### Solución Propuesta
En `src/darius_ai/core/agent_planner.py:378-381`:
```python
elif action == "hotkey":
    keys = p.get("keys", "enter")
    key_list = [k.strip() for k in re.split(r"[,+\s]+", keys) if k.strip()]
    gui.human_hotkey(*key_list)
    return True, f"Atajo ejecutado: {' + '.join(key_list)}"
```

#### Criterios de Aceptación (DoD)
- [ ] Combinaciones compuestas como `"ctrl+c"`, `"win+r"`, `"alt+tab"` se dividen y envían como argumentos independientes a `gui.human_hotkey`.
- [ ] Test unitario específico en `tests/test_agent_planner.py` verificando que `gui.human_hotkey` recibe `("ctrl", "c")`.

---

# 🟠 BLOQUE 2: SEGURIDAD, SANDBOX Y CI/CD

---

### ISSUE #4: [CI/CD] Ruptura del Gate 1 de CI: 20 violaciones de Ruff bloquean integración continua en GitHub Actions

- **Título**: `[CI/CD] Ruptura del Gate 1 de CI: 20 violaciones de Ruff bloquean integración continua`
- **Etiquetas**: `ci/cd`, `high`, `tech-debt`
- **Prioridad**: Alta
- **Módulos**: Configuración de CI, múltiples archivos en `src/` y `tests/`

#### Descripción
El flujo de integración continua `.github/workflows/main_darius-ai.yml` ejecuta `ruff check --output-format=github .` en el Gate 1 (Ubuntu 3.11). Actualmente existen 20 errores de linter que impiden que cualquier pull request o push a la rama `main` complete el pipeline de pruebas de Windows.

#### Detalle de Violaciones Detectadas
```
src\darius_ai\gui\app.py:1289:37: UP015 Unnecessary mode argument
src\darius_ai\gui\bento_dashboard.py:457:19: E741 Ambiguous variable name: l
src\darius_ai\gui\byok_settings.py:140:1: W293 Blank line contains whitespace
src\darius_ai\gui\floating_voice_capsule.py:16:1: I001 Import block is un-sorted or un-formatted
src\darius_ai\gui\floating_voice_capsule.py:202:1: W293 Blank line contains whitespace
src\darius_ai\gui\gui_theme.py:9:1: I001 Import block is un-sorted or un-formatted
src\darius_ai\gui\human_gui.py:23:1: E402 Module level import not at top of file
tests\test_tts_worker.py:75:121: E501 Line too long (129 > 120)
tests\test_ui_ux_audit_fixes.py:19:1: I001 Import block is un-sorted
tests\test_ui_ux_audit_fixes.py:53:121: E501 Line too long (123 > 120)
tests\test_ui_ux_audit_fixes.py:68, 72, 76, 80: W293 Blank line contains whitespace
tests\test_ui_ux_audit_fixes.py:123, 207, 285, 311: I001 Import block is un-sorted
tests\test_ui_ux_audit_fixes.py:324, 327: W293 Blank line contains whitespace
```

#### Solución Propuesta
1. Ejecutar correcciones automáticas: `ruff check --fix .`.
2. Corregir manualmente `E741` en `bento_dashboard.py`: renombrar `(l, t, r, b)` a `(left, top, right, bottom)`.
3. Partir las líneas largas (>120 caracteres) en `test_tts_worker.py` y `test_ui_ux_audit_fixes.py`.
4. Corregir `E402` en `human_gui.py` ubicando imports conforme al estándar PEP 8.

#### Criterios de Aceptación (DoD)
- [ ] `ruff check .` finaliza con 0 errores y código de salida 0.
- [ ] El workflow de GitHub Actions ejecuta Gate 1 con luz verde.

---

### ISSUE #5: [SECURITY] `SafeCodeInterpreter` vulnerable a agotamiento de memoria (DoS) y evasión de AST mediante `str.format()`

- **Título**: `[SECURITY] SafeCodeInterpreter vulnerable a agotamiento de memoria (DoS) y evasión mediante str.format()`
- **Etiquetas**: `security`, `high`, `sandbox`
- **Prioridad**: Alta
- **Módulos**: `src/darius_ai/core/safe_code_interpreter.py`

#### Descripción
El intérprete seguro de Python `SafeCodeInterpreter` evalúa código generado por LLMs o scripts locales. Presenta dos vectores de vulnerabilidad:
1. **Denegación de Servicio (DoS) por OOM**: Se ejecuta en un hilo dentro del mismo proceso Python que la aplicación gráfica. Operaciones que asignan gigabytes de memoria (ej. `[0] * (10**9)`) agotan la memoria del proceso y colapsan la interfaz completa de Darius.
2. **Evasión de análisis estático AST mediante evaluación tardía**: Aunque `ASTValidator` prohíbe atributos privados que inicien con `_`, cadenas de formato evaluadas en tiempo de ejecución por `str.format()` eluden la validación de nodos `ast.Attribute`:
   ```python
   # Pasa la validación AST porque '__class__' es un string literal:
   x = "{0.__class__.__base__}".format(1)  # Retorna <class 'object'>
   s = "{0.__globals__}".format(f)  # Filtra el diccionario de globales
   ```

#### Solución Propuesta
1. Agregar validación en AST para nodos `ast.Constant` o `ast.Str` que contengan patrones de interpolación con dunders: `r"\{[^}]*__[a-zA-Z0-9_]+__[^}]*\}"`.
2. Considerar el aislamiento de la ejecución en un proceso independiente (`multiprocessing.Process` o subproceso aislado) con límite estricto de memoria para evitar que un OOM destruya el proceso principal de la GUI.

#### Criterios de Aceptación (DoD)
- [ ] Patrones de formato con introspección dunder son rechazados por `UnsafeCodeError`.
- [ ] La ejecución de código con consumo masivo de memoria no derriba la ventana principal.
- [ ] Tests de regresión añadidos en `tests/test_safe_code_interpreter.py`.

---

### ISSUE #6: [SECURITY] Almacenamiento en texto plano de claves de API de LLM y TTS en `config.json` sin Windows DPAPI

- **Título**: `[SECURITY] Almacenamiento en texto plano de claves de API en config.json sin Windows DPAPI`
- **Etiquetas**: `security`, `high`, `credentials`
- **Prioridad**: Alta
- **Módulos**: `src/darius_ai/core/config_loader.py`

#### Descripción
Las credenciales sensibles de los proveedores BYOK (`gemini_api_key`, `openai_api_key`, `openrouter_api_key`, `nvidia_api_key`, `groq_api_key`, `elevenlabs_api_key`) se persisten en texto plano en el archivo de configuración JSON (`.darius_data/config.json` o `%APPDATA%/DariusAI/config.json`). Cualquier software malicioso en el espacio de usuario puede exfiltrar estas claves sin necesidad de privilegios elevados.

#### Solución Propuesta
Integrar protección criptográfica a nivel de sistema operativo para Windows:
1. Usar la API nativa de Windows **DPAPI** (`CryptProtectData` y `CryptUnprotectData` vía `ctypes.windll.crypt32`), que vincula las claves al hash del usuario de Windows sin requerir contraseñas maestras.
2. Alternativamente, utilizar la librería estándar `keyring` para delegar el almacenamiento seguro en el Administrador de Credenciales de Windows (Windows Credential Manager).
3. Mantener retrocompatibilidad transparente descifrando al cargar y cifrando al guardar.

#### Criterios de Aceptación (DoD)
- [ ] Las claves de API no aparecen en texto claro dentro de `config.json` en disco.
- [ ] El asistente puede descifrar las claves en tiempo de ejecución de manera transparente para el usuario legítimo de la sesión.

---

### ISSUE #7: [BUG/SECURITY] Regla de detección de `elevenlabs_key` en `CredentialStripper` provoca falsos positivos en hashes MD5 y UUIDs

- **Título**: `[BUG/SECURITY] Regla de elevenlabs_key en CredentialStripper ofusca hashes MD5 legítimos y UUIDs`
- **Etiquetas**: `bug`, `medium`, `security`
- **Prioridad**: Media
- **Módulos**: `src/darius_ai/core/security_guard.py`

#### Descripción
En `src/darius_ai/core/security_guard.py:209`:
```python
(("elevenlabs_key", re.compile(r"\b[a-f0-9]{32}\b")),)
```
Al carecer de un prefijo identificador (a diferencia de `sk-`, `AIzaSy`, `ghp_`), cualquier cadena de 32 caracteres hexadecimales —como sumas de verificación MD5, identificadores de trazas distribuidas OpenTelemetry, ETags HTTP o hashes criptográficos de archivos— es detectada erróneamente como una clave de ElevenLabs y reemplazada por `[REDACTED:elevenlabs_key]`.

#### Consecuencia
En consultas técnicas donde el usuario pide verificar el checksum MD5 de una descarga, o cuando se analizan logs del sistema, los hashes quedan destruidos en el chat y en las herramientas agénticas.

#### Solución Propuesta
1. Requerir contexto contextual o límites semánticos para ElevenLabs (por ejemplo, validar si va precedida de etiquetas comunes en JSON/cabeceras como `xi-api-key`, `elevenlabs`, `api_key`).
2. O bien, utilizar el detector estricto solo en entradas de configuración, evitando ofuscar texto genérico si no hay coincidencia de entropía o contexto de autenticación.

#### Criterios de Aceptación (DoD)
- [ ] Cadenas como `d41d8cd98f00b204e9800998ecf8427e` en texto general no son ofuscadas a menos que exista contexto explícito de clave API.
- [ ] Test unitario en `tests/test_security_guard.py` con hashes MD5 preservados.

---

### ISSUE #8: [BUG] Falla de Barge-In en `EdgeTTS` al reproducir audio mediante Win32 MCI bloqueante

- **Título**: `[BUG] Falla de Barge-In en EdgeTTS al reproducir audio mediante Win32 MCI bloqueante`
- **Etiquetas**: `bug`, `medium`, `audio`
- **Prioridad**: Media
- **Módulos**: `src/darius_ai/audio/edge_tts_engine.py`, `src/darius_ai/audio/tts_worker.py`

#### Descripción
Al usar el motor `EdgeTTS`, la reproducción de archivos temporales de audio en Windows se delega a Win32 MCI:
```python
winmm.mciSendStringW(f"play {alias} wait", None, 0, None)
```
El parámetro `wait` bloquea la ejecución de la función hasta que el archivo MP3 termina de reproducirse.  
Cuando el usuario activa la interrupción vocal (Barge-in) presionando `Escape` o pulsando el botón de micrófono, `TTSWorker.interrupt()` purga SAPI 5 y llama a `sounddevice.stop()`, pero no envía la orden de parada a Win32 MCI. Como resultado, la voz de Edge-TTS sigue hablando y no puede ser interrumpida.

#### Solución Propuesta
En `TTSWorker.interrupt()` (`src/darius_ai/audio/tts_worker.py`):
```python
if sys.platform == "win32":
    with contextlib.suppress(Exception):
        import ctypes

        ctypes.windll.winmm.mciSendStringW("stop all", None, 0, None)
        ctypes.windll.winmm.mciSendStringW("close all", None, 0, None)
```

#### Criterios de Aceptación (DoD)
- [ ] La invocación de `TTSWorker.interrupt()` detiene de forma instantánea cualquier reproducción en curso en Win32 MCI.
- [ ] La tecla `Escape` o el clic de micrófono aborta inmediatamente la alocución con Edge-TTS.

---

# 🟡 BLOQUE 3: ARQUITECTURA, CONCURRENCIA Y PRUEBAS

---

### ISSUE #9: [ARCH] Monolito God Class en `src/darius_ai/gui/app.py` (2,567 líneas violando SRP)

- **Título**: `[ARCH] Desacoplar clase monolítica DariusFinal en app.py (2,567 líneas)`
- **Etiquetas**: `refactor`, `high`, `architecture`
- **Prioridad**: Alta
- **Módulos**: `src/darius_ai/gui/app.py`

#### Descripción
La clase `DariusFinal` en `app.py` abarca más de 2,500 líneas y centraliza más de 10 responsabilidades que violan el Principio de Responsabilidad Única (SRP):
- Construcción y maquetación de la GUI en CustomTkinter.
- Captura de audio y bucle de reconocimiento STT (`speech_recognition`).
- Control de volumen de Windows y llamadas Win32 / pycaw.
- Despacho y evaluación de expresiones regulares de comandos del SO.
- Lanzamiento de hilos sin supervisión para visión, deep research y scraping.
- Conexión a la bóveda de Obsidian y diario.
- Llamadas y gestión de historial de LLMs.

#### Consecuencia
Cualquier modificación menor en expresiones regulares o en la interfaz corre el riesgo de generar regresiones en el pipeline de renderizado de 60 FPS o en el ciclo de vida del audio. Las pruebas unitarias requieren mocks masivos de hardware y ventanas gráficas.

#### Plan de Refactorización
Extraer componentes siguiendo el patrón Mediator / Presentation Model:
1. `src/darius_ai/controllers/command_controller.py`: Despacho de comandos, regexes y confirmaciones destructivas.
2. `src/darius_ai/controllers/audio_lifecycle_controller.py`: Manejo de micrófono, PTT, STT y TTS worker.
3. `src/darius_ai/gui/views/`: Subvistas especializadas (`chat_view.py`, `dashboard_view.py`, `workspaces_view.py`, `obsidian_view.py`, `logs_view.py`).
4. `app.py`: Shell ligero (<350 líneas) que inicializa la ventana y vincula eventos.

---

### ISSUE #10: [ARCH] Invocaciones residuales al módulo deprecado `src.darius_ai.gui.human_gui` en subsistemas internos

- **Título**: `[ARCH] Migrar imports internos residuales de gui.human_gui a automation.human_input`
- **Etiquetas**: `refactor`, `medium`, `cleanup`
- **Prioridad**: Media
- **Módulos**: `agentic_bridge.py`, `agent_planner.py`, `app.py`, `gui/human_gui.py`

#### Descripción
El módulo de automatización de interfaz (`HumanGUIAutomator`) fue reubicado arquitectónicamente a `src/darius_ai/automation/human_input.py`, dejando `src/darius_ai/gui/human_gui.py` únicamente como un proxy deprecado que emite `DeprecationWarning`.  
Sin embargo, módulos internos de producción (`agentic_bridge.py`, `agent_planner.py` y `app.py`) continúan importando desde `src.darius_ai.gui.human_gui`, inundando los logs de advertencias y manteniendo acoplamiento indebido.

#### Archivos y Líneas Afectadas
- `src/darius_ai/core/agentic_bridge.py`: Líneas 237, 253, 265, 276, 293
- `src/darius_ai/core/agent_planner.py`: Línea 371
- `src/darius_ai/gui/app.py`: Líneas 2094, 2110, 2126, 2322
- `src/darius_ai/gui/human_gui.py`: Línea 23 (infracción E402)

#### Solución Propuesta
1. Reemplazar todas las importaciones internas por `from src.darius_ai.automation.human_input import gui`.
2. En `src/darius_ai/gui/human_gui.py`, colocar los imports al inicio y el `warnings.warn` posterior para cumplir con PEP 8 y eliminar el error E402 de Ruff.

---

### ISSUE #11: [BUG] Dependencia no declarada `'soundfile'` causa `ImportError` en fallback de reproducción de audio

- **Título**: `[BUG] Dependencia no declarada 'soundfile' en requirements.txt para fallback de audio`
- **Etiquetas**: `bug`, `medium`, `dependencies`
- **Prioridad**: Media
- **Módulos**: `requirements.txt`, `src/darius_ai/audio/edge_tts_engine.py`

#### Descripción
En `src/darius_ai/audio/edge_tts_engine.py:56`:
```python
try:
    import sounddevice as sd
    import soundfile as sf
    data, fs = sf.read(target_str)
```
Si el reproductor Win32 MCI falla o no está disponible, el sistema intenta utilizar `sounddevice` junto a `soundfile`. Sin embargo, `soundfile` no está incluido en `requirements.txt` ni instalado en el entorno virtual, provocando un `ModuleNotFoundError: No module named 'soundfile'`.

#### Solución Propuesta
Añadir `soundfile>=0.12.1` a la sección de motores de audio en `requirements.txt`.

---

### ISSUE #12: [TESTS] Salto silencioso del test de sincronización de patrones en `tests/test_commands_v6.py`

- **Título**: `[TESTS] Salto silencioso de TestPatternsMatchMain en test_commands_v6.py`
- **Etiquetas**: `testing`, `medium`
- **Prioridad**: Media
- **Módulos**: `tests/test_commands_v6.py`, `src/darius_ai/gui/app.py`

#### Descripción
En `tests/test_commands_v6.py:1027`:
```python
try:
    from main import _CMD_PATTERNS as _REAL_PATTERNS

    MAIN_PATTERNS_AVAILABLE = True
except Exception:
    MAIN_PATTERNS_AVAILABLE = False
```
El test `TestPatternsMatchMain` verifica que la lista de patrones de comando del código de producción coincida exactamente con los casos de prueba unitarios para prevenir desincronizaciones. Dado que `_CMD_PATTERNS` se trasladó de `main.py` a `src/darius_ai/gui/app.py`, la importación fallaba silenciosamente y la clase de prueba era omitida (`skipped`) en cada ejecución de la suite.

#### Solución Propuesta
Actualizar la importación en `tests/test_commands_v6.py`:
```python
try:
    from src.darius_ai.gui.app import _CMD_PATTERNS as _REAL_PATTERNS

    MAIN_PATTERNS_AVAILABLE = True
except Exception:
    MAIN_PATTERNS_AVAILABLE = False
```

---

### ISSUE #13: [CONCURRENCY] Condición de carrera en `conversation_history` ante eventos concurrentes de voz y texto

- **Título**: `[CONCURRENCY] Condición de carrera en conversation_history por accesos multi-hilo concurrentes`
- **Etiquetas**: `bug`, `medium`, `threading`
- **Prioridad**: Media
- **Módulos**: `src/darius_ai/gui/app.py`

#### Descripción
En `app.py`, las consultas a los modelos de IA se ejecutan en hilos demonio desacoplados (`name="gemini"`). Si el usuario ingresa texto por teclado mientras finaliza una captura de voz, se instancian dos hilos en paralelo que ejecutan `ask_gemini()`. Ambos hilos mutan y leen la lista `self.conversation_history` sin ningún bloqueo de exclusión mutua (`Lock`). Esto puede producir turnos de conversación desordenados, descarte de mensajes o excepciones de concurrencia al rebanar la lista.

#### Solución Propuesta
Declarar `self._history_lock = threading.Lock()` en `DariusFinal.__init__()` y envolver con `with self._history_lock:` todas las operaciones de inserción, lectura y truncado de `self.conversation_history`.

---

# 🔵 BLOQUE 4: PORTABILIDAD, RELEASE Y RENDIMIENTO

---

### ISSUE #14: [PORTABILITY] Rutas absolutas del desarrollador hardcodeadas en `ai_client.py` para contexto de proyectos

- **Título**: `[PORTABILITY] Rutas de proyectos locales hardcodeadas para el usuario 'Oscar'`
- **Etiquetas**: `portability`, `low`, `enhancement`
- **Prioridad**: Baja
- **Módulos**: `src/darius_ai/core/ai_client.py`

#### Descripción
En `src/darius_ai/core/ai_client.py:234-238`:
```python
user_home = pathlib.Path.home()
roots = [
    user_home / "Documents" / "Proyectos Personales GH",
    user_home / "Documents" / "Proyectos Colaboración GH",
]
```
La función de inyección de contexto de proyectos busca rutas fijas específicas de la máquina del desarrollador original. En equipos de otros usuarios, estas carpetas no existen y la inyección contextual no opera.

#### Solución Propuesta
Permitir configurar las rutas en `config.json` mediante la clave `"project_roots": []`, con fallback a los directorios predeterminados si no se especifica ninguno.

---

### ISSUE #15: [RELEASE] Desincronización de versión v8.5.0 en scripts de compilación, instalador Inno Setup y release workflow

- **Título**: `[RELEASE] Sincronizar versión v8.5.0 en build_nuitka.py, installer.iss y release.yml`
- **Etiquetas**: `release`, `low`, `documentation`
- **Prioridad**: Baja
- **Módulos**: `build_nuitka.py`, `installer.iss`, `.github/workflows/release.yml`, `SECURITY.md`

#### Descripción
Aunque el proyecto está en la versión **8.5.0** (declarada en `pyproject.toml`, `gui_theme.py` y `CHANGELOG.md`), los archivos de soporte de empaquetado conservan residuos de la v7.1.0:
- `build_nuitka.py:19`: `os.environ.get("GITHUB_REF_NAME", "7.1.0")`
- `build_nuitka.py:32`: `DARIUS AI — COMPILACIÓN NATIVA STANDALONE CON NUITKA (v7.1.0)`
- `installer.iss:8`: `#define MyAppVersion "7.1.0"`
- `installer.iss:15`: `AppId={{D4R1U5-A1-W1ND0W5-V710}}`
- `installer.iss:27`: `#define MyOutputBaseFilename "DariusAI-Setup-v7.1.0"`
- `.github/workflows/release.yml:12`: `default: 'v7.1.0'`
- `SECURITY.md:7`: La tabla de versiones solo cubre hasta `7.x`.

#### Solución Propuesta
Actualizar las cadenas por defecto a `8.5.0` y regenerar el `AppId` de Inno Setup para v8.5.0.

---

### ISSUE #16: [PERF] Bloqueo síncrono de I/O en hilo principal de UI durante telemetría de disco y red en `BentoDashboard`

- **Título**: `[PERF] Ejecución síncrona de psutil.disk_usage en el hilo principal de Tkinter`
- **Etiquetas**: `performance`, `low`, `gui`
- **Prioridad**: Baja
- **Módulos**: `src/darius_ai/gui/bento_dashboard.py`

#### Descripción
En `src/darius_ai/gui/bento_dashboard.py:725-735`, el temporizador `_tick_hardware` se programa con `self.after(2000, self._tick_hardware)` directamente en el hilo de la GUI y realiza llamadas síncronas a `psutil.disk_usage("C:\\")` y `psutil.net_io_counters()`. Cuando el disco C: se encuentra bajo carga intensiva (ej. compilaciones o descargas), estas llamadas al kernel de Windows pueden demorarse entre 50ms y 250ms, generando micro-congelamientos perceptibles en las animaciones de 60 FPS del Cyber Core.

#### Solución Propuesta
Mover la lectura de telemetría de hardware a un hilo en segundo plano que actualice una estructura en memoria protegida por mutex, y en la GUI leer los valores ya en caché con `self.after(0)`.

---

### ISSUE #17: [UI/TOKENS] Fragmentación de colores y omisión de tokens de diseño en `byok_settings.py`

- **Título**: `[UI/TOKENS] Reemplazar colores hexadecimales hardcodeados en byok_settings.py por tokens de gui_theme`
- **Etiquetas**: `ui/ux`, `low`, `design-tokens`
- **Prioridad**: Baja
- **Módulos**: `src/darius_ai/gui/byok_settings.py`, `src/darius_ai/gui/gui_theme.py`

#### Descripción
En la ventana modal de configuración BYOK (`byok_settings.py`), se declaran valores hexadecimales directos (`#090D16`, `#111827`, `#1F2937`) para el fondo y las tarjetas en lugar de consumir las constantes canónicas de `src/darius_ai/gui/gui_theme.py` (`BG_CANVAS`, `BG_CARD`, `BG_CARD_INNER`), violando la coherencia del sistema de diseño unificado.

#### Solución Propuesta
Reemplazar los colores hardcodeados por sus equivalentes semánticos en `gui_theme.py`.

---

## 🎯 RESUMEN DE ACCIÓN Y ROADMAP RECOMENDADO

1. **Sprint 1 (Parches Inmediatos / Hotfixes)**:
   - Resolver Issue #1 (Contrato de scraping web).
   - Resolver Issue #2 (TypeError en human_click).
   - Resolver Issue #3 (Tokenización de hotkeys en AgentPlanner).
   - Resolver Issue #4 (Corregir los 20 errores de Ruff para habilitar CI).
   - Resolver Issue #12 (Import de test_commands_v6.py).

2. **Sprint 2 (Seguridad y Concurrencia)**:
   - Resolver Issue #5 (Sandbox AST format string bypass & memoria).
   - Resolver Issue #6 (Cifrado DPAPI de credenciales).
   - Resolver Issue #7 (Falsos positivos de ElevenLabs regex).
   - Resolver Issue #8 (Barge-in para Win32 MCI).
   - Resolver Issue #13 (Mutex para conversation_history).

3. **Sprint 3 (Arquitectura & Release)**:
   - Resolver Issue #9 (Modularización de app.py God Class).
   - Resolver Issue #10 (Limpieza de imports de human_gui).
   - Resolver Issue #11 (Agregar soundfile a requirements.txt).
   - Resolver Issue #15 (Sincronización de versión v8.5.0 en instaladores).
   - Resolver Issue #16 (Telemetría psutil en hilo secundario).
